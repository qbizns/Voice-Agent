using System.Threading.Tasks;
using UnityEngine;
using VoiceAgent.Networking;
using VoiceAgent.Data;

namespace VoiceAgent.Examples
{
    /// <summary>
    /// Simple demo showing how to use the Voice Agent client
    /// Attach to an empty GameObject in your scene
    /// </summary>
    public class SimpleVoiceAgentDemo : MonoBehaviour
    {
        [Header("References")]
        [Tooltip("Voice Agent Client (will be found automatically if not assigned)")]
        public VoiceAgentClient client;

        [Header("Test Messages")]
        [Tooltip("Test messages to send (press keys 1-5)")]
        public string[] testMessages = new string[]
        {
            "مرحباً، كيف حالك؟",
            "ما هو الطقس اليوم؟",
            "أخبرني عن نفسك",
            "ما هي أحدث المعلومات؟",
            "شكراً لك"
        };

        private void Start()
        {
            // Find client if not assigned
            if (client == null)
            {
                client = FindObjectOfType<VoiceAgentClient>();
            }

            if (client == null)
            {
                Debug.LogError("VoiceAgentClient not found! Add it to your scene.");
                return;
            }

            // Subscribe to events
            client.OnConnected += OnConnected;
            client.OnDisconnected += OnDisconnected;
            client.OnTranscriptionReceived += OnTranscription;
            client.OnResponseReceived += OnResponse;
            client.OnError += OnError;
        }

        private void Update()
        {
            if (client == null || !client.IsConnected) return;

            // Press 1-5 to send test messages
            for (int i = 0; i < testMessages.Length && i < 5; i++)
            {
                if (Input.GetKeyDown(KeyCode.Alpha1 + i))
                {
                    SendMessage(testMessages[i]);
                }
            }

            // Press C to connect/disconnect
            if (Input.GetKeyDown(KeyCode.C))
            {
                if (client.IsConnected)
                {
                    _ = client.DisconnectAsync();
                }
                else
                {
                    _ = client.ConnectAsync();
                }
            }

            // Press P to send ping
            if (Input.GetKeyDown(KeyCode.P))
            {
                _ = client.SendPing();
                Debug.Log("Ping sent");
            }
        }

        private async void SendMessage(string message)
        {
            Debug.Log($"<color=cyan>Sending: {message}</color>");
            await client.SendTextMessage(message);
        }

        #region Event Handlers

        private void OnConnected()
        {
            Debug.Log("<color=green><b>Connected to Voice Agent!</b></color>");
            Debug.Log("Press 1-5 to send test messages");
        }

        private void OnDisconnected()
        {
            Debug.Log("<color=yellow>Disconnected from Voice Agent</color>");
        }

        private void OnTranscription(TranscriptionData data)
        {
            Debug.Log($"<color=yellow>Transcription: {data.text}</color>");
        }

        private void OnResponse(ResponseData data)
        {
            Debug.Log($"<color=lime><b>Agent Response:</b> {data.text}</color>");

            if (data.visemes != null && data.visemes.Count > 0)
            {
                Debug.Log($"Visemes: {data.visemes.Count} frames");
            }

            if (data.sources != null && data.sources.Count > 0)
            {
                Debug.Log($"Sources: {string.Join(", ", data.sources)}");
            }

            Debug.Log($"Performance: Total={data.processingTimes.totalMs:F0}ms, " +
                     $"AI={data.processingTimes.aiGenerationMs:F0}ms, " +
                     $"TTS={data.processingTimes.synthesisMs:F0}ms, " +
                     $"LipSync={data.processingTimes.lipsyncMs:F0}ms");
        }

        private void OnError(string error)
        {
            Debug.LogError($"<color=red>Error: {error}</color>");
        }

        #endregion

        private void OnGUI()
        {
            if (client == null) return;

            GUILayout.BeginArea(new Rect(10, 10, 400, 300));

            // Connection status
            string status = client.IsConnected ? "<color=green>Connected</color>" : "<color=red>Disconnected</color>";
            GUILayout.Label($"<b>Voice Agent Status:</b> {status}");

            GUILayout.Space(10);

            // Instructions
            GUILayout.Label("<b>Controls:</b>");
            GUILayout.Label("C - Connect/Disconnect");
            GUILayout.Label("P - Send Ping");
            GUILayout.Label("1-5 - Send Test Messages:");

            for (int i = 0; i < testMessages.Length && i < 5; i++)
            {
                GUILayout.Label($"  {i + 1}. {testMessages[i]}");
            }

            GUILayout.EndArea();
        }
    }
}
