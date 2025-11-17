using System;
using System.Collections;
using System.IO;
using UnityEngine;
using UnityEngine.Networking;

namespace VoiceAgent.Audio
{
    /// <summary>
    /// Utility for decoding and playing audio from bytes (MP3/WAV)
    /// </summary>
    public static class AudioStreamPlayer
    {
        /// <summary>
        /// Play audio from byte array (WAV or MP3)
        /// NOTE: Unity doesn't decode MP3 at runtime on most platforms.
        /// Recommended: Configure backend to send WAV instead.
        /// </summary>
        public static IEnumerator PlayAudioFromBytes(
            byte[] audioBytes,
            AudioSource audioSource,
            Action<AudioClip> onAudioClipReady = null,
            Action<string> onError = null)
        {
            // Detect audio format (simple check - first 4 bytes)
            bool isWav = audioBytes.Length > 4 &&
                         audioBytes[0] == 'R' &&
                         audioBytes[1] == 'I' &&
                         audioBytes[2] == 'F' &&
                         audioBytes[3] == 'F';

            bool isMp3 = audioBytes.Length > 2 &&
                         ((audioBytes[0] == 0xFF && (audioBytes[1] & 0xE0) == 0xE0) || // MP3 frame sync
                          (audioBytes[0] == 'I' && audioBytes[1] == 'D' && audioBytes[2] == '3')); // ID3 tag

            if (isWav)
            {
                yield return LoadWavFromBytes(audioBytes, audioSource, onAudioClipReady, onError);
            }
            else if (isMp3)
            {
                yield return LoadMp3FromBytes(audioBytes, audioSource, onAudioClipReady, onError);
            }
            else
            {
                string error = "Unknown audio format (not WAV or MP3)";
                Debug.LogError(error);
                onError?.Invoke(error);
            }
        }

        /// <summary>
        /// Load WAV file from bytes (Unity native support)
        /// </summary>
        private static IEnumerator LoadWavFromBytes(
            byte[] wavBytes,
            AudioSource audioSource,
            Action<AudioClip> onReady,
            Action<string> onError)
        {
            try
            {
                // Create temporary file (Unity can load WAV from file)
                string tempPath = Path.Combine(Application.temporaryCachePath, $"temp_audio_{Guid.NewGuid()}.wav");
                File.WriteAllBytes(tempPath, wavBytes);

                // Load using UnityWebRequest
                string url = $"file://{tempPath}";
                using (UnityWebRequest www = UnityWebRequestMultimedia.GetAudioClip(url, AudioType.WAV))
                {
                    yield return www.SendWebRequest();

                    if (www.result == UnityWebRequest.Result.Success)
                    {
                        AudioClip clip = DownloadHandlerAudioClip.GetContent(www);

                        if (clip != null)
                        {
                            audioSource.clip = clip;
                            audioSource.Play();
                            onReady?.Invoke(clip);
                        }
                        else
                        {
                            string error = "Failed to create AudioClip from WAV";
                            Debug.LogError(error);
                            onError?.Invoke(error);
                        }
                    }
                    else
                    {
                        string error = $"Failed to load WAV: {www.error}";
                        Debug.LogError(error);
                        onError?.Invoke(error);
                    }
                }

                // Cleanup temp file
                if (File.Exists(tempPath))
                {
                    File.Delete(tempPath);
                }
            }
            catch (Exception e)
            {
                string error = $"WAV decode error: {e.Message}";
                Debug.LogError(error);
                onError?.Invoke(error);
            }
        }

        /// <summary>
        /// Load MP3 file from bytes (Unity WebGL/Mobile/Standalone support varies)
        /// </summary>
        private static IEnumerator LoadMp3FromBytes(
            byte[] mp3Bytes,
            AudioSource audioSource,
            Action<AudioClip> onReady,
            Action<string> onError)
        {
#if UNITY_WEBGL && !UNITY_EDITOR
            // WebGL can decode MP3 via browser
            yield return LoadMp3WebGL(mp3Bytes, audioSource, onReady, onError);
#elif UNITY_IOS || UNITY_ANDROID
            // Mobile platforms can decode MP3
            yield return LoadMp3Mobile(mp3Bytes, audioSource, onReady, onError);
#else
            // Standalone: Use UnityWebRequest (works on some platforms)
            // For best cross-platform support, recommend using WAV from backend
            yield return LoadMp3Standalone(mp3Bytes, audioSource, onReady, onError);
#endif
        }

        private static IEnumerator LoadMp3Standalone(
            byte[] mp3Bytes,
            AudioSource audioSource,
            Action<AudioClip> onReady,
            Action<string> onError)
        {
            try
            {
                // Create temporary file
                string tempPath = Path.Combine(Application.temporaryCachePath, $"temp_audio_{Guid.NewGuid()}.mp3");
                File.WriteAllBytes(tempPath, mp3Bytes);

                // Load using UnityWebRequest
                string url = $"file://{tempPath}";
                using (UnityWebRequest www = UnityWebRequestMultimedia.GetAudioClip(url, AudioType.MPEG))
                {
                    yield return www.SendWebRequest();

                    if (www.result == UnityWebRequest.Result.Success)
                    {
                        AudioClip clip = DownloadHandlerAudioClip.GetContent(www);

                        if (clip != null)
                        {
                            audioSource.clip = clip;
                            audioSource.Play();
                            onReady?.Invoke(clip);
                        }
                        else
                        {
                            string error = "Failed to create AudioClip from MP3. " +
                                         "Consider configuring backend to send WAV instead.";
                            Debug.LogError(error);
                            onError?.Invoke(error);
                        }
                    }
                    else
                    {
                        string error = $"Failed to load MP3: {www.error}. " +
                                     "MP3 support varies by platform. Recommend using WAV.";
                        Debug.LogError(error);
                        onError?.Invoke(error);
                    }
                }

                // Cleanup
                if (File.Exists(tempPath))
                {
                    File.Delete(tempPath);
                }
            }
            catch (Exception e)
            {
                string error = $"MP3 decode error: {e.Message}";
                Debug.LogError(error);
                onError?.Invoke(error);
            }
        }

        private static IEnumerator LoadMp3Mobile(
            byte[] mp3Bytes,
            AudioSource audioSource,
            Action<AudioClip> onReady,
            Action<string> onError)
        {
            // Mobile platforms generally support MP3
            yield return LoadMp3Standalone(mp3Bytes, audioSource, onReady, onError);
        }

        private static IEnumerator LoadMp3WebGL(
            byte[] mp3Bytes,
            AudioSource audioSource,
            Action<AudioClip> onReady,
            Action<string> onError)
        {
            // WebGL supports MP3 via browser
            yield return LoadMp3Standalone(mp3Bytes, audioSource, onReady, onError);
        }

        /// <summary>
        /// Alternative: Decode WAV from byte array directly (without temp file)
        /// Supports standard PCM WAV format
        /// </summary>
        public static AudioClip LoadWavDirect(byte[] wavBytes, string clipName = "RemoteAudio")
        {
            try
            {
                // Parse WAV header
                int channels = BitConverter.ToInt16(wavBytes, 22);
                int sampleRate = BitConverter.ToInt32(wavBytes, 24);
                int byteRate = BitConverter.ToInt32(wavBytes, 28);
                int bitsPerSample = BitConverter.ToInt16(wavBytes, 34);

                // Find data chunk
                int dataStart = 44; // Standard WAV header size
                int dataSize = BitConverter.ToInt32(wavBytes, 40);

                // Convert bytes to float samples
                int sampleCount = dataSize / (bitsPerSample / 8);
                float[] samples = new float[sampleCount];

                if (bitsPerSample == 16)
                {
                    for (int i = 0; i < sampleCount; i++)
                    {
                        short sample = BitConverter.ToInt16(wavBytes, dataStart + i * 2);
                        samples[i] = sample / 32768f; // Convert to -1.0 to 1.0
                    }
                }
                else if (bitsPerSample == 8)
                {
                    for (int i = 0; i < sampleCount; i++)
                    {
                        byte sample = wavBytes[dataStart + i];
                        samples[i] = (sample - 128) / 128f; // Convert to -1.0 to 1.0
                    }
                }
                else
                {
                    Debug.LogError($"Unsupported WAV bit depth: {bitsPerSample}");
                    return null;
                }

                // Create AudioClip
                AudioClip clip = AudioClip.Create(clipName, samples.Length / channels, channels, sampleRate, false);
                clip.SetData(samples, 0);

                return clip;
            }
            catch (Exception e)
            {
                Debug.LogError($"Failed to decode WAV directly: {e.Message}");
                return null;
            }
        }
    }
}
