using System;
using System.Threading.Tasks;
using UnityEngine;
using NativeWebSocket;
using Newtonsoft.Json;
using Newtonsoft.Json.Linq;
using VoiceAgent.Data;
using VoiceAgent.LipSync;
using VoiceAgent.Audio;

namespace VoiceAgent.Networking
{
    /// <summary>
    /// WebSocket client for Voice Agent backend
    /// Handles connection, message sending/receiving, and event dispatching
    /// </summary>
    public class VoiceAgentClient : MonoBehaviour
    {
        [Header("Connection")]
        [Tooltip("WebSocket server URL (e.g., ws://localhost:8000/api/v1/ws/conversation)")]
        public string serverUrl = "ws://localhost:8000/api/v1/ws/conversation";

        [Tooltip("Auto-connect on Start()")]
        public bool autoConnect = true;

        [Tooltip("Reconnect automatically on disconnect")]
        public bool autoReconnect = true;

        [Tooltip("Reconnect delay in seconds")]
        public float reconnectDelay = 5f;

        [Header("References")]
        [Tooltip("Lip-sync controller for character animation")]
        public LipSyncController lipSyncController;

        [Tooltip("Audio source for playing responses")]
        public AudioSource audioSource;

        [Header("Debug")]
        public bool logMessages = true;

        // Events
        public event Action OnConnected;
        public event Action OnDisconnected;
        public event Action<TranscriptionData> OnTranscriptionReceived;
        public event Action<ResponseData> OnResponseReceived;
        public event Action<string> OnError;
        public event Action<string> OnInfo;

        // State
        private WebSocket webSocket;
        private bool isConnected = false;
        private bool shouldReconnect = false;

        // Properties
        public bool IsConnected => isConnected;

        private async void Start()
        {
            if (autoConnect)
            {
                await ConnectAsync();
            }
        }

        private void Update()
        {
            // Required for NativeWebSocket to dispatch messages on main thread
            if (webSocket != null)
            {
#if !UNITY_WEBGL || UNITY_EDITOR
                webSocket.DispatchMessageQueue();
#endif
            }
        }

        /// <summary>
        /// Connect to the WebSocket server
        /// </summary>
        public async Task ConnectAsync()
        {
            if (isConnected)
            {
                LogMessage("Already connected");
                return;
            }

            try
            {
                LogMessage($"Connecting to {serverUrl}...");

                webSocket = new WebSocket(serverUrl);

                // Setup event handlers
                webSocket.OnOpen += OnWebSocketOpen;
                webSocket.OnClose += OnWebSocketClose;
                webSocket.OnMessage += OnWebSocketMessage;
                webSocket.OnError += OnWebSocketError;

                // Connect
                await webSocket.Connect();
            }
            catch (Exception e)
            {
                LogError($"Connection failed: {e.Message}");
                OnError?.Invoke($"Connection failed: {e.Message}");
            }
        }

        /// <summary>
        /// Disconnect from the WebSocket server
        /// </summary>
        public async Task DisconnectAsync()
        {
            shouldReconnect = false;

            if (webSocket != null && webSocket.State == WebSocketState.Open)
            {
                await webSocket.Close();
            }

            isConnected = false;
        }

        /// <summary>
        /// Send a text message to the agent
        /// </summary>
        public async Task SendTextMessage(string text)
        {
            if (!isConnected)
            {
                LogError("Not connected to server");
                return;
            }

            try
            {
                var message = new TextMessageRequest
                {
                    data = text
                };

                string json = JsonConvert.SerializeObject(message);
                LogMessage($"Sending text: {text}");

                await webSocket.SendText(json);
            }
            catch (Exception e)
            {
                LogError($"Failed to send text message: {e.Message}");
                OnError?.Invoke($"Send failed: {e.Message}");
            }
        }

        /// <summary>
        /// Send audio data to the agent (base64 encoded)
        /// </summary>
        public async Task SendAudioMessage(byte[] audioData)
        {
            if (!isConnected)
            {
                LogError("Not connected to server");
                return;
            }

            try
            {
                string audioBase64 = Convert.ToBase64String(audioData);

                var message = new AudioMessageRequest
                {
                    data = audioBase64
                };

                string json = JsonConvert.SerializeObject(message);
                LogMessage($"Sending audio ({audioData.Length} bytes)");

                await webSocket.SendText(json);
            }
            catch (Exception e)
            {
                LogError($"Failed to send audio message: {e.Message}");
                OnError?.Invoke($"Send failed: {e.Message}");
            }
        }

        /// <summary>
        /// Send ping to keep connection alive
        /// </summary>
        public async Task SendPing()
        {
            if (!isConnected) return;

            var message = new { type = MessageType.Ping };
            string json = JsonConvert.SerializeObject(message);
            await webSocket.SendText(json);
        }

        #region WebSocket Event Handlers

        private void OnWebSocketOpen()
        {
            isConnected = true;
            shouldReconnect = autoReconnect;
            LogMessage("Connected to server");
            OnConnected?.Invoke();
        }

        private void OnWebSocketClose(WebSocketCloseCode closeCode)
        {
            isConnected = false;
            LogMessage($"Disconnected from server (code: {closeCode})");
            OnDisconnected?.Invoke();

            if (shouldReconnect)
            {
                Invoke(nameof(AttemptReconnect), reconnectDelay);
            }
        }

        private void OnWebSocketMessage(byte[] data)
        {
            try
            {
                string json = System.Text.Encoding.UTF8.GetString(data);
                ProcessMessage(json);
            }
            catch (Exception e)
            {
                LogError($"Failed to process message: {e.Message}");
            }
        }

        private void OnWebSocketError(string errorMsg)
        {
            LogError($"WebSocket error: {errorMsg}");
            OnError?.Invoke(errorMsg);
        }

        #endregion

        #region Message Processing

        private void ProcessMessage(string json)
        {
            try
            {
                // Parse base message to get type
                JObject obj = JObject.Parse(json);
                string messageType = obj["type"]?.ToString();

                if (string.IsNullOrEmpty(messageType))
                {
                    LogError("Message has no type field");
                    return;
                }

                LogMessage($"Received: {messageType}");

                switch (messageType)
                {
                    case MessageType.Transcription:
                        HandleTranscription(obj["data"]);
                        break;

                    case MessageType.Response:
                        HandleResponse(obj["data"]);
                        break;

                    case MessageType.Error:
                        HandleError(obj["data"]);
                        break;

                    case MessageType.Info:
                        HandleInfo(obj["data"]);
                        break;

                    case MessageType.Pong:
                        // Pong received (keep-alive response)
                        break;

                    default:
                        LogMessage($"Unknown message type: {messageType}");
                        break;
                }
            }
            catch (Exception e)
            {
                LogError($"Failed to process message: {e.Message}\nJSON: {json}");
            }
        }

        private void HandleTranscription(JToken data)
        {
            try
            {
                var transcription = data.ToObject<TranscriptionData>();
                LogMessage($"Transcription: {transcription.text}");
                OnTranscriptionReceived?.Invoke(transcription);
            }
            catch (Exception e)
            {
                LogError($"Failed to parse transcription: {e.Message}");
            }
        }

        private void HandleResponse(JToken data)
        {
            try
            {
                var response = data.ToObject<ResponseData>();

                LogMessage($"Response: {response.text}");
                LogMessage($"Processing times: Total={response.processingTimes.totalMs}ms, " +
                          $"LipSync={response.processingTimes.lipsyncMs}ms");

                // Decode audio
                if (!string.IsNullOrEmpty(response.audioBase64))
                {
                    byte[] audioBytes = Convert.FromBase64String(response.audioBase64);

                    // Play audio with lip-sync
                    PlayResponseAudio(audioBytes, response.visemes);
                }

                OnResponseReceived?.Invoke(response);
            }
            catch (Exception e)
            {
                LogError($"Failed to parse response: {e.Message}");
            }
        }

        private void HandleError(JToken data)
        {
            try
            {
                var error = data.ToObject<ErrorData>();
                LogError($"Server error: {error.message}");
                OnError?.Invoke(error.message);
            }
            catch (Exception e)
            {
                LogError($"Failed to parse error: {e.Message}");
            }
        }

        private void HandleInfo(JToken data)
        {
            try
            {
                string message = data["message"]?.ToString() ?? data.ToString();
                LogMessage($"Info: {message}");
                OnInfo?.Invoke(message);
            }
            catch (Exception e)
            {
                LogError($"Failed to parse info: {e.Message}");
            }
        }

        #endregion

        #region Audio & Lip-Sync Playback

        private void PlayResponseAudio(byte[] audioBytes, System.Collections.Generic.List<VisemeFrame> visemes)
        {
            if (audioSource == null)
            {
                LogError("AudioSource not assigned");
                return;
            }

            // Decode audio (MP3 -> AudioClip)
            // Note: Unity doesn't natively decode MP3 at runtime. Options:
            // 1. Use backend WAV output (easier)
            // 2. Use native plugin (NAudio on Windows, AVFoundation on iOS/Mac)
            // 3. Use third-party plugin (RuntimeAudioClipLoader, UnityWebRequest for streaming)

            // For now, assume backend sends WAV (configure backend to output WAV)
            StartCoroutine(AudioStreamPlayer.PlayAudioFromBytes(
                audioBytes,
                audioSource,
                onAudioClipReady: (clip) =>
                {
                    // Start lip-sync animation
                    if (lipSyncController != null && visemes != null && visemes.Count > 0)
                    {
                        lipSyncController.PlayVisemeTimeline(visemes, audioSource);
                    }
                },
                onError: (error) =>
                {
                    LogError($"Failed to decode audio: {error}");
                }
            ));
        }

        #endregion

        #region Reconnection

        private async void AttemptReconnect()
        {
            if (!shouldReconnect || isConnected) return;

            LogMessage("Attempting to reconnect...");
            await ConnectAsync();
        }

        #endregion

        #region Logging

        private void LogMessage(string message)
        {
            if (logMessages)
            {
                Debug.Log($"[VoiceAgentClient] {message}");
            }
        }

        private void LogError(string message)
        {
            Debug.LogError($"[VoiceAgentClient] {message}");
        }

        #endregion

        #region Cleanup

        private async void OnDestroy()
        {
            shouldReconnect = false;
            await DisconnectAsync();
        }

        private async void OnApplicationQuit()
        {
            shouldReconnect = false;
            await DisconnectAsync();
        }

        #endregion
    }
}
