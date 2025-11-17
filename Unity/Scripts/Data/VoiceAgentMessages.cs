using System;
using System.Collections.Generic;
using Newtonsoft.Json;

namespace VoiceAgent.Data
{
    /// <summary>
    /// Viseme keyframe with timestamp and weight
    /// </summary>
    [Serializable]
    public class VisemeFrame
    {
        [JsonProperty("time_ms")]
        public float timeMs;

        [JsonProperty("id")]
        public string id;

        [JsonProperty("weight")]
        public float weight = 1.0f;

        /// <summary>
        /// Time in seconds (for Unity AudioSource.time)
        /// </summary>
        public float TimeSeconds => timeMs / 1000f;
    }

    /// <summary>
    /// Processing times for performance monitoring
    /// </summary>
    [Serializable]
    public class ProcessingTimes
    {
        [JsonProperty("transcription_ms")]
        public float transcriptionMs;

        [JsonProperty("ai_generation_ms")]
        public float aiGenerationMs;

        [JsonProperty("synthesis_ms")]
        public float synthesisMs;

        [JsonProperty("lipsync_ms")]
        public float lipsyncMs;

        [JsonProperty("total_ms")]
        public float totalMs;
    }

    /// <summary>
    /// Transcription data from STT
    /// </summary>
    [Serializable]
    public class TranscriptionData
    {
        [JsonProperty("text")]
        public string text;

        [JsonProperty("confidence")]
        public float? confidence;

        [JsonProperty("processing_time_ms")]
        public float processingTimeMs;
    }

    /// <summary>
    /// Response data from AI agent
    /// </summary>
    [Serializable]
    public class ResponseData
    {
        [JsonProperty("text")]
        public string text;

        [JsonProperty("audio")]
        public string audioBase64;

        [JsonProperty("visemes")]
        public List<VisemeFrame> visemes;

        [JsonProperty("sources")]
        public List<string> sources;

        [JsonProperty("processing_times")]
        public ProcessingTimes processingTimes;
    }

    /// <summary>
    /// WebSocket message wrapper
    /// </summary>
    [Serializable]
    public class WebSocketMessage
    {
        [JsonProperty("type")]
        public string type;

        [JsonProperty("data")]
        public object data;

        [JsonProperty("timestamp")]
        public float? timestamp;
    }

    /// <summary>
    /// Message types
    /// </summary>
    public static class MessageType
    {
        public const string Audio = "audio";
        public const string Text = "text";
        public const string Transcription = "transcription";
        public const string Response = "response";
        public const string Error = "error";
        public const string Info = "info";
        public const string Ping = "ping";
        public const string Pong = "pong";
    }

    /// <summary>
    /// Client->Server text message
    /// </summary>
    [Serializable]
    public class TextMessageRequest
    {
        [JsonProperty("type")]
        public string type = MessageType.Text;

        [JsonProperty("data")]
        public string data;
    }

    /// <summary>
    /// Client->Server audio message
    /// </summary>
    [Serializable]
    public class AudioMessageRequest
    {
        [JsonProperty("type")]
        public string type = MessageType.Audio;

        [JsonProperty("data")]
        public string data; // base64 audio
    }

    /// <summary>
    /// Error message from server
    /// </summary>
    [Serializable]
    public class ErrorData
    {
        [JsonProperty("message")]
        public string message;
    }
}
