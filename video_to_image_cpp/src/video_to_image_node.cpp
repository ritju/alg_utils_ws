/**
 * @file video_to_image_node.cpp
 * @brief Video to Image ROS2 Node (C++)
 *
 * Converts video files to sensor_msgs::msg::Image or CompressedImage
 * and publishes to specified topics with timestamps from /clock.
 * Also supports converting compressed image topics to raw image topics.
 * Supports multiple video/topic pairs via array parameters.
 */

#include <rclcpp/rclcpp.hpp>
#include <sensor_msgs/msg/image.hpp>
#include <sensor_msgs/msg/compressed_image.hpp>
#include <cv_bridge/cv_bridge.h>
#include <opencv2/opencv.hpp>
#include <string>
#include <filesystem>
#include <memory>
#include <vector>

namespace fs = std::filesystem;

class VideoToImageNode : public rclcpp::Node
{
public:
    VideoToImageNode() : Node("video_to_image_node")
    {
        // Declare parameters
        this->declare_parameter("input_source", "video");  // "video" or "compress_topic"
        this->declare_parameter("video_path", std::vector<std::string>{});
        this->declare_parameter("output_topic", std::vector<std::string>{"/camera/image_raw"});
        this->declare_parameter("publish_compressed", false);
        this->declare_parameter("compressed_topic", std::vector<std::string>{"/camera/image_raw/compressed"});
        this->declare_parameter("frame_rate", 30.0);
        this->declare_parameter("width", 640);
        this->declare_parameter("height", 480);
        this->declare_parameter("loop", true);
        this->declare_parameter("frame_id", "camera");
        this->declare_parameter("timestamp_offset", 0.01);
        this->declare_parameter("loan", false);

        // Get parameters
        input_source_ = this->get_parameter("input_source").as_string();
        video_paths_ = this->get_parameter("video_path").as_string_array();
        output_topics_ = this->get_parameter("output_topic").as_string_array();
        publish_compressed_ = this->get_parameter("publish_compressed").as_bool();
        compressed_topics_ = this->get_parameter("compressed_topic").as_string_array();
        frame_rate_ = this->get_parameter("frame_rate").as_double();
        target_width_ = this->get_parameter("width").as_int();
        target_height_ = this->get_parameter("height").as_int();
        loop_ = this->get_parameter("loop").as_bool();
        frame_id_ = this->get_parameter("frame_id").as_string();
        timestamp_offset_ = this->get_parameter("timestamp_offset").as_double();
        loan_ = this->get_parameter("loan").as_bool();

        // Validate array lengths based on input_source
        validate_array_lengths();

        // Create QoS profile
        rclcpp::QoS qos_profile(3);
        qos_profile.reliability(rclcpp::ReliabilityPolicy::BestEffort);
        qos_profile.durability(rclcpp::DurabilityPolicy::Volatile);
        qos_profile.history(rclcpp::HistoryPolicy::KeepLast);

        if (input_source_ == "compress_topic")
        {
            // Mode: compressed image topic -> raw image topic
            setup_compress_topic_mode(qos_profile);
        }
        else
        {
            // Mode: video file -> image topic (default)
            setup_video_mode(qos_profile);
        }

        bool use_sim_time = this->get_parameter("use_sim_time").as_bool();
        RCLCPP_INFO(this->get_logger(), "use_sim_time: %s", use_sim_time ? "true" : "false");
        if (use_sim_time)
        {
            RCLCPP_INFO(this->get_logger(), "Using /clock topic for timestamps");
        }
        RCLCPP_INFO(this->get_logger(), "Video to Image node started (input_source: %s)", input_source_.c_str());
    }

    void validate_array_lengths()
    {
        if (input_source_ == "video")
        {
            // For video mode: video_paths, output_topics, compressed_topics must have same length
            if (video_paths_.empty())
            {
                RCLCPP_ERROR(this->get_logger(), "video_path parameter is required for video mode!");
                throw std::runtime_error("video_path parameter is required for video mode!");
            }

            size_t n = video_paths_.size();
            if (output_topics_.size() != n)
            {
                RCLCPP_ERROR(this->get_logger(),
                    "Array length mismatch: video_path has %zu elements, output_topic has %zu elements",
                    n, output_topics_.size());
                throw std::runtime_error("Array length mismatch between video_path and output_topic!");
            }

            if (compressed_topics_.size() != n)
            {
                RCLCPP_ERROR(this->get_logger(),
                    "Array length mismatch: video_path has %zu elements, compressed_topic has %zu elements",
                    n, compressed_topics_.size());
                throw std::runtime_error("Array length mismatch between video_path and compressed_topic!");
            }
        }
        else if (input_source_ == "compress_topic")
        {
            // For compress_topic mode: compressed_topics (input) and output_topics must have same length
            if (compressed_topics_.empty())
            {
                RCLCPP_ERROR(this->get_logger(), "compressed_topic parameter is required for compress_topic mode!");
                throw std::runtime_error("compressed_topic parameter is required for compress_topic mode!");
            }

            size_t n = compressed_topics_.size();
            if (output_topics_.size() != n)
            {
                RCLCPP_ERROR(this->get_logger(),
                    "Array length mismatch: compressed_topic has %zu elements, output_topic has %zu elements",
                    n, output_topics_.size());
                throw std::runtime_error("Array length mismatch between compressed_topic and output_topic!");
            }
        }
    }

    void setup_video_mode(const rclcpp::QoS &qos_profile)
    {
        // Initialize video streams for each video path
        for (size_t i = 0; i < video_paths_.size(); ++i)
        {
            const std::string &video_path = video_paths_[i];
            const std::string &output_topic = output_topics_[i];
            const std::string &compressed_topic = compressed_topics_[i];

            // Validate video path
            if (video_path.empty())
            {
                RCLCPP_ERROR(this->get_logger(), "video_path[%zu] is empty!", i);
                throw std::runtime_error("video_path[" + std::to_string(i) + "] is empty!");
            }

            if (!fs::exists(video_path))
            {
                RCLCPP_ERROR(this->get_logger(), "Video file not found: %s", video_path.c_str());
                throw std::runtime_error("Video file not found: " + video_path);
            }

            // Create VideoStream instance
            auto stream = std::make_shared<VideoStream>();
            stream->video_path = video_path;
            stream->output_topic = output_topic;
            stream->compressed_topic = compressed_topic;

            if (publish_compressed_)
            {
                stream->compressed_publisher = this->create_publisher<sensor_msgs::msg::CompressedImage>(
                    compressed_topic, qos_profile);
                RCLCPP_INFO(this->get_logger(), "[%zu] Publishing compressed images to: %s",
                            i, compressed_topic.c_str());
            }
            else
            {
                stream->image_publisher = this->create_publisher<sensor_msgs::msg::Image>(
                    output_topic, qos_profile);
                RCLCPP_INFO(this->get_logger(), "[%zu] Publishing raw images to: %s",
                            i, output_topic.c_str());
            }

            // Open video file
            stream->cap.open(video_path);
            if (!stream->cap.isOpened())
            {
                RCLCPP_ERROR(this->get_logger(), "Failed to open video: %s", video_path.c_str());
                throw std::runtime_error("Failed to open video: " + video_path);
            }

            // Get video properties
            stream->video_fps = stream->cap.get(cv::CAP_PROP_FPS);
            stream->video_frame_count = static_cast<int>(stream->cap.get(cv::CAP_PROP_FRAME_COUNT));
            stream->video_width = static_cast<int>(stream->cap.get(cv::CAP_PROP_FRAME_WIDTH));
            stream->video_height = static_cast<int>(stream->cap.get(cv::CAP_PROP_FRAME_HEIGHT));

            RCLCPP_INFO(this->get_logger(),
                        "[%zu] Video loaded: %s\n"
                        "  Resolution: %dx%d\n"
                        "  FPS: %.2f\n"
                        "  Frames: %d",
                        i, video_path.c_str(), stream->video_width, stream->video_height,
                        stream->video_fps, stream->video_frame_count);
            RCLCPP_INFO(this->get_logger(), "[%zu] Target resolution: %dx%d",
                        i, target_width_, target_height_);

            stream->frame_count = 0;
            video_streams_.push_back(stream);
        }

        // Calculate frame interval based on desired frame rate
        frame_interval_ = 1.0 / frame_rate_;

        // Create timer for publishing frames
        timer_ = this->create_wall_timer(
            std::chrono::duration<double>(frame_interval_),
            std::bind(&VideoToImageNode::timer_callback, this));
    }

    void setup_compress_topic_mode(const rclcpp::QoS &qos_profile)
    {
        // Create subscribers and publishers for each topic pair
        for (size_t i = 0; i < compressed_topics_.size(); ++i)
        {
            const std::string &compressed_topic = compressed_topics_[i];
            const std::string &output_topic = output_topics_[i];

            auto stream = std::make_shared<TopicStream>();
            stream->output_topic = output_topic;
            stream->compressed_input_topic = compressed_topic;

            // Publisher for raw images
            stream->image_publisher = this->create_publisher<sensor_msgs::msg::Image>(
                output_topic, qos_profile);
            RCLCPP_INFO(this->get_logger(), "[%zu] Publishing raw images to: %s", i, output_topic.c_str());

            // Subscriber for compressed images
            stream->compressed_subscriber = this->create_subscription<sensor_msgs::msg::CompressedImage>(
                compressed_topic, qos_profile,
                [this, stream](const sensor_msgs::msg::CompressedImage::SharedPtr msg) {
                    this->compressed_image_callback(msg, stream->image_publisher);
                });
            RCLCPP_INFO(this->get_logger(), "[%zu] Subscribing to compressed images from: %s",
                        i, compressed_topic.c_str());

            topic_streams_.push_back(stream);
        }
    }

    ~VideoToImageNode()
    {
        for (auto &stream : video_streams_)
        {
            if (stream->cap.isOpened())
            {
                stream->cap.release();
            }
        }
    }

private:
    // Structure to hold video stream data
    struct VideoStream
    {
        std::string video_path;
        std::string output_topic;
        std::string compressed_topic;
        cv::VideoCapture cap;
        double video_fps;
        int video_frame_count;
        int video_width;
        int video_height;
        int frame_count;
        rclcpp::Publisher<sensor_msgs::msg::Image>::SharedPtr image_publisher;
        rclcpp::Publisher<sensor_msgs::msg::CompressedImage>::SharedPtr compressed_publisher;
    };

    // Structure to hold topic stream data
    struct TopicStream
    {
        std::string output_topic;
        std::string compressed_input_topic;
        rclcpp::Publisher<sensor_msgs::msg::Image>::SharedPtr image_publisher;
        rclcpp::Subscription<sensor_msgs::msg::CompressedImage>::SharedPtr compressed_subscriber;
    };

    void timer_callback()
    {
        for (auto &stream : video_streams_)
        {
            cv::Mat frame;
            bool ret = stream->cap.read(frame);

            if (!ret)
            {
                if (loop_)
                {
                    RCLCPP_INFO(this->get_logger(), "Video ended, looping: %s", stream->video_path.c_str());
                    stream->cap.set(cv::CAP_PROP_POS_FRAMES, 0);
                    ret = stream->cap.read(frame);
                    if (!ret)
                    {
                        RCLCPP_ERROR(this->get_logger(), "Failed to restart video: %s", stream->video_path.c_str());
                        continue;
                    }
                }
                else
                {
                    RCLCPP_INFO(this->get_logger(), "Video ended, stopping: %s", stream->video_path.c_str());
                    continue;
                }
            }

            // Resize frame to target resolution
            if (target_width_ != stream->video_width || target_height_ != stream->video_height)
            {
                cv::resize(frame, frame, cv::Size(target_width_, target_height_), 0, 0, cv::INTER_LINEAR);
            }

            // Get timestamp from ROS clock with offset adjustment
            rclcpp::Time timestamp = this->now();
            timestamp = rclcpp::Time(timestamp.nanoseconds() +
                                    static_cast<int64_t>(timestamp_offset_ * 1e9));

            if (publish_compressed_)
            {
                publish_compressed_image(frame, timestamp, stream->compressed_publisher);
            }
            else
            {
                publish_raw_image(frame, timestamp, stream->image_publisher);
            }

            stream->frame_count++;
        }

        // Check if all videos have ended (in non-loop mode)
        if (!loop_)
        {
            bool all_ended = true;
            for (const auto &stream : video_streams_)
            {
                if (stream->cap.isOpened())
                {
                    all_ended = false;
                    break;
                }
            }
            if (all_ended)
            {
                timer_->cancel();
            }
        }
    }

    void compressed_image_callback(const sensor_msgs::msg::CompressedImage::SharedPtr msg,
                                   rclcpp::Publisher<sensor_msgs::msg::Image>::SharedPtr publisher)
    {
        // Decode compressed image using cv_bridge
        cv_bridge::CvImagePtr cv_ptr;
        try
        {
            cv_ptr = cv_bridge::toCvCopy(msg);
        }
        catch (const cv_bridge::Exception &e)
        {
            RCLCPP_ERROR(this->get_logger(), "cv_bridge exception: %s", e.what());
            return;
        }

        // Convert to Image message and publish
        sensor_msgs::msg::Image::SharedPtr image_msg = cv_ptr->toImageMsg();
        publisher->publish(*image_msg);
    }

    void publish_raw_image(const cv::Mat &frame, const rclcpp::Time &timestamp,
                          rclcpp::Publisher<sensor_msgs::msg::Image>::SharedPtr publisher)
    {
        // Convert BGR to RGB
        cv::Mat frame_rgb;
        cv::cvtColor(frame, frame_rgb, cv::COLOR_BGR2RGB);

        if (loan_)
        {
            auto loaned_msg = publisher->borrow_loaned_message();
            loaned_msg.get().header.stamp = timestamp;
            loaned_msg.get().header.frame_id = frame_id_;
            loaned_msg.get().height = frame_rgb.rows;
            loaned_msg.get().width = frame_rgb.cols;
            loaned_msg.get().encoding = "rgb8";
            loaned_msg.get().is_bigendian = false;
            loaned_msg.get().step = frame_rgb.cols * 3;
            loaned_msg.get().data.assign(frame_rgb.datastart, frame_rgb.dataend);
            publisher->publish(std::move(loaned_msg));
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
            publisher->publish(std::move(msg));
        }
    }

    void publish_compressed_image(const cv::Mat &frame, const rclcpp::Time &timestamp,
                                 rclcpp::Publisher<sensor_msgs::msg::CompressedImage>::SharedPtr publisher)
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
            auto loaned_msg = publisher->borrow_loaned_message();
            loaned_msg.get().header.stamp = timestamp;
            loaned_msg.get().header.frame_id = frame_id_;
            loaned_msg.get().format = "jpeg";
            loaned_msg.get().data = encoded;
            publisher->publish(std::move(loaned_msg));
        }
        else
        {
            auto msg = std::make_unique<sensor_msgs::msg::CompressedImage>();
            msg->header.stamp = timestamp;
            msg->header.frame_id = frame_id_;
            msg->format = "jpeg";
            msg->data = encoded;
            publisher->publish(std::move(msg));
        }
    }

    // Parameters
    std::string input_source_;
    std::vector<std::string> video_paths_;
    std::vector<std::string> output_topics_;
    bool publish_compressed_;
    std::vector<std::string> compressed_topics_;
    double frame_rate_;
    int target_width_;
    int target_height_;
    bool loop_;
    std::string frame_id_;
    double timestamp_offset_;
    bool loan_;

    // Timer and frame interval
    rclcpp::TimerBase::SharedPtr timer_;
    double frame_interval_;

    // Video streams (for video mode)
    std::vector<std::shared_ptr<VideoStream>> video_streams_;

    // Topic streams (for compress_topic mode)
    std::vector<std::shared_ptr<TopicStream>> topic_streams_;
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