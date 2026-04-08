/**
 * @file video_to_image_node.cpp
 * @brief Video to Image ROS2 Node (C++)
 *
 * Converts video files to sensor_msgs::msg::Image or CompressedImage
 * and publishes to specified topics with timestamps from /clock.
 */

#include <rclcpp/rclcpp.hpp>
#include <sensor_msgs/msg/image.hpp>
#include <sensor_msgs/msg/compressed_image.hpp>
#include <cv_bridge/cv_bridge.h>
#include <opencv2/opencv.hpp>
#include <string>
#include <filesystem>
#include <memory>

namespace fs = std::filesystem;

class VideoToImageNode : public rclcpp::Node
{
public:
    VideoToImageNode() : Node("video_to_image_node")
    {
        // Declare parameters
        this->declare_parameter("video_path", "");
        this->declare_parameter("output_topic", "/camera/image_raw");
        this->declare_parameter("publish_compressed", false);
        this->declare_parameter("compressed_topic", "/camera/image_raw/compressed");
        this->declare_parameter("frame_rate", 30.0);
        this->declare_parameter("width", 640);
        this->declare_parameter("height", 480);
        this->declare_parameter("loop", true);
        this->declare_parameter("frame_id", "camera");
        this->declare_parameter("timestamp_offset", 0.01);
        this->declare_parameter("loan", false);

        // Get parameters
        video_path_ = this->get_parameter("video_path").as_string();
        output_topic_ = this->get_parameter("output_topic").as_string();
        publish_compressed_ = this->get_parameter("publish_compressed").as_bool();
        compressed_topic_ = this->get_parameter("compressed_topic").as_string();
        frame_rate_ = this->get_parameter("frame_rate").as_double();
        target_width_ = this->get_parameter("width").as_int();
        target_height_ = this->get_parameter("height").as_int();
        loop_ = this->get_parameter("loop").as_bool();
        frame_id_ = this->get_parameter("frame_id").as_string();
        timestamp_offset_ = this->get_parameter("timestamp_offset").as_double();
        loan_ = this->get_parameter("loan").as_bool();

        // Validate video path
        if (video_path_.empty())
        {
            RCLCPP_ERROR(this->get_logger(), "video_path parameter is required!");
            throw std::runtime_error("video_path parameter is required!");
        }

        if (!fs::exists(video_path_))
        {
            RCLCPP_ERROR(this->get_logger(), "Video file not found: %s", video_path_.c_str());
            throw std::runtime_error("Video file not found: " + video_path_);
        }

        // Create publishers with volatile QoS
        rclcpp::QoS qos_profile(3);
        qos_profile.reliability(rclcpp::ReliabilityPolicy::BestEffort);
        qos_profile.durability(rclcpp::DurabilityPolicy::Volatile);
        qos_profile.history(rclcpp::HistoryPolicy::KeepLast);

        if (publish_compressed_)
        {
            compressed_publisher_ = this->create_publisher<sensor_msgs::msg::CompressedImage>(
                compressed_topic_, qos_profile);
            RCLCPP_INFO(this->get_logger(), "Publishing compressed images to: %s",
                        compressed_topic_.c_str());
        }
        else
        {
            image_publisher_ = this->create_publisher<sensor_msgs::msg::Image>(
                output_topic_, qos_profile);
            RCLCPP_INFO(this->get_logger(), "Publishing raw images to: %s",
                        output_topic_.c_str());
        }

        // Open video file
        cap_.open(video_path_);
        if (!cap_.isOpened())
        {
            RCLCPP_ERROR(this->get_logger(), "Failed to open video: %s", video_path_.c_str());
            throw std::runtime_error("Failed to open video: " + video_path_);
        }

        // Get video properties
        video_fps_ = cap_.get(cv::CAP_PROP_FPS);
        video_frame_count_ = static_cast<int>(cap_.get(cv::CAP_PROP_FRAME_COUNT));
        video_width_ = static_cast<int>(cap_.get(cv::CAP_PROP_FRAME_WIDTH));
        video_height_ = static_cast<int>(cap_.get(cv::CAP_PROP_FRAME_HEIGHT));

        RCLCPP_INFO(this->get_logger(),
                    "Video loaded: %s\n"
                    "  Resolution: %dx%d\n"
                    "  FPS: %.2f\n"
                    "  Frames: %d",
                    video_path_.c_str(), video_width_, video_height_,
                    video_fps_, video_frame_count_);
        RCLCPP_INFO(this->get_logger(), "Target resolution: %dx%d",
                    target_width_, target_height_);

        // Calculate frame interval based on desired frame rate
        frame_interval_ = 1.0 / frame_rate_;

        // Create timer for publishing frames
        timer_ = this->create_wall_timer(
            std::chrono::duration<double>(frame_interval_),
            std::bind(&VideoToImageNode::timer_callback, this));

        // Frame counter for timing
        frame_count_ = 0;

        bool use_sim_time = this->get_parameter("use_sim_time").as_bool();
        RCLCPP_INFO(this->get_logger(), "use_sim_time: %s", use_sim_time ? "true" : "false");
        if (use_sim_time)
        {
            RCLCPP_INFO(this->get_logger(), "Using /clock topic for timestamps");
        }
        RCLCPP_INFO(this->get_logger(), "Video to Image node started");
    }

    ~VideoToImageNode()
    {
        if (cap_.isOpened())
        {
            cap_.release();
        }
    }

private:
    void timer_callback()
    {
        cv::Mat frame;
        bool ret = cap_.read(frame);

        if (!ret)
        {
            if (loop_)
            {
                RCLCPP_INFO(this->get_logger(), "Video ended, looping...");
                cap_.set(cv::CAP_PROP_POS_FRAMES, 0);
                ret = cap_.read(frame);
                if (!ret)
                {
                    RCLCPP_ERROR(this->get_logger(), "Failed to restart video");
                    return;
                }
            }
            else
            {
                RCLCPP_INFO(this->get_logger(), "Video ended, stopping...");
                timer_->cancel();
                return;
            }
        }

        // Resize frame to target resolution
        if (target_width_ != video_width_ || target_height_ != video_height_)
        {
            cv::resize(frame, frame, cv::Size(target_width_, target_height_), 0, 0, cv::INTER_LINEAR);
        }

        // Get timestamp from ROS clock with offset adjustment
        rclcpp::Time timestamp = this->now();
        timestamp = rclcpp::Time(timestamp.nanoseconds() +
                                static_cast<int64_t>(timestamp_offset_ * 1e9));

        if (publish_compressed_)
        {
            publish_compressed_image(frame, timestamp);
        }
        else
        {
            publish_raw_image(frame, timestamp);
        }

        frame_count_++;
    }

    void publish_raw_image(const cv::Mat &frame, const rclcpp::Time &timestamp)
    {
        // Convert BGR to RGB
        cv::Mat frame_rgb;
        cv::cvtColor(frame, frame_rgb, cv::COLOR_BGR2RGB);

        if (loan_)
        {
            auto loaned_msg = image_publisher_->borrow_loaned_message();
            loaned_msg.get().header.stamp = timestamp;
            loaned_msg.get().header.frame_id = frame_id_;
            loaned_msg.get().height = frame_rgb.rows;
            loaned_msg.get().width = frame_rgb.cols;
            loaned_msg.get().encoding = "rgb8";
            loaned_msg.get().is_bigendian = false;
            loaned_msg.get().step = frame_rgb.cols * 3;
            loaned_msg.get().data.assign(frame_rgb.datastart, frame_rgb.dataend);
            image_publisher_->publish(std::move(loaned_msg));
        }
        else
        {
            auto msg = std::make_unique<sensor_msgs::msg::Image>();
            msg->header.stamp = timestamp;
            msg->header.frame_id = frame_id_;
            msg->height = frame_rgb.rows;
            msg->width = frame_rgb.cols;
            msg->encoding = "rgb8";
            msg->is_bigendian = false;
            msg->step = frame_rgb.cols * 3;
            msg->data.assign(frame_rgb.datastart, frame_rgb.dataend);
            image_publisher_->publish(std::move(msg));
        }
    }

    void publish_compressed_image(const cv::Mat &frame, const rclcpp::Time &timestamp)
    {
        // Encode frame as JPEG
        std::vector<uint8_t> encoded;
        std::vector<int> params = {cv::IMWRITE_JPEG_QUALITY, 90};
        if (!cv::imencode(".jpg", frame, encoded, params))
        {
            RCLCPP_ERROR(this->get_logger(), "Failed to encode frame as JPEG");
            return;
        }

        if (loan_)
        {
            auto loaned_msg = compressed_publisher_->borrow_loaned_message();
            loaned_msg.get().header.stamp = timestamp;
            loaned_msg.get().header.frame_id = frame_id_;
            loaned_msg.get().format = "jpeg";
            loaned_msg.get().data = encoded;
            compressed_publisher_->publish(std::move(loaned_msg));
        }
        else
        {
            auto msg = std::make_unique<sensor_msgs::msg::CompressedImage>();
            msg->header.stamp = timestamp;
            msg->header.frame_id = frame_id_;
            msg->format = "jpeg";
            msg->data = encoded;
            compressed_publisher_->publish(std::move(msg));
        }
    }

    // Parameters
    std::string video_path_;
    std::string output_topic_;
    bool publish_compressed_;
    std::string compressed_topic_;
    double frame_rate_;
    int target_width_;
    int target_height_;
    bool loop_;
    std::string frame_id_;
    double timestamp_offset_;
    bool loan_;

    // Video capture
    cv::VideoCapture cap_;
    double video_fps_;
    int video_frame_count_;
    int video_width_;
    int video_height_;

    // Timer and frame counter
    rclcpp::TimerBase::SharedPtr timer_;
    int frame_count_;
    double frame_interval_;

    // Publishers
    rclcpp::Publisher<sensor_msgs::msg::Image>::SharedPtr image_publisher_;
    rclcpp::Publisher<sensor_msgs::msg::CompressedImage>::SharedPtr compressed_publisher_;
};

int main(int argc, char **argv)
{
    rclcpp::init(argc, argv);

    try
    {
        auto node = std::make_shared<VideoToImageNode>();
        rclcpp::spin(node);
    }
    catch (const std::exception &e)
    {
        std::cerr << "Error: " << e.what() << std::endl;
        rclcpp::shutdown();
        return 1;
    }

    rclcpp::shutdown();
    return 0;
}