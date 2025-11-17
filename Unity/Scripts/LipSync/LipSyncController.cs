using System.Collections;
using System.Collections.Generic;
using System.Linq;
using UnityEngine;
using VoiceAgent.Data;

namespace VoiceAgent.LipSync
{
    /// <summary>
    /// Controls lip-sync animation by applying viseme weights to blendshapes
    /// synchronized with audio playback
    /// </summary>
    [RequireComponent(typeof(SkinnedMeshRenderer))]
    public class LipSyncController : MonoBehaviour
    {
        [Header("Blendshape Configuration")]
        [Tooltip("SkinnedMeshRenderer with face blendshapes")]
        public SkinnedMeshRenderer faceRenderer;

        [Tooltip("Viseme to blendshape mappings")]
        public List<VisemeBlendshapeMapping> visemeMappings = new List<VisemeBlendshapeMapping>
        {
            new VisemeBlendshapeMapping { visemeId = "A", blendshapeIndex = -1 },
            new VisemeBlendshapeMapping { visemeId = "B", blendshapeIndex = -1 },
            new VisemeBlendshapeMapping { visemeId = "C", blendshapeIndex = -1 },
            new VisemeBlendshapeMapping { visemeId = "D", blendshapeIndex = -1 },
            new VisemeBlendshapeMapping { visemeId = "E", blendshapeIndex = -1 },
            new VisemeBlendshapeMapping { visemeId = "F", blendshapeIndex = -1 },
            new VisemeBlendshapeMapping { visemeId = "G", blendshapeIndex = -1 },
            new VisemeBlendshapeMapping { visemeId = "H", blendshapeIndex = -1 },
            new VisemeBlendshapeMapping { visemeId = "X", blendshapeIndex = -1 }
        };

        [Header("Animation Settings")]
        [Tooltip("Smoothing speed for blendshape transitions (higher = faster)")]
        [Range(1f, 50f)]
        public float smoothingSpeed = 10f;

        [Tooltip("Maximum blendshape weight (Unity blendshapes use 0-100 scale)")]
        [Range(0f, 100f)]
        public float maxBlendshapeWeight = 100f;

        [Tooltip("Weight multiplier for all visemes")]
        [Range(0f, 2f)]
        public float globalWeightMultiplier = 1.0f;

        [Tooltip("Reset mouth to neutral when not playing")]
        public bool resetOnStop = true;

        [Header("Debug")]
        public bool showDebugInfo = false;
        public bool drawGizmos = false;

        // Runtime state
        private List<VisemeFrame> currentTimeline;
        private AudioSource currentAudioSource;
        private bool isPlaying = false;
        private int currentVisemeIndex = 0;
        private Dictionary<int, float> targetBlendshapeWeights = new Dictionary<int, float>();
        private Dictionary<int, float> currentBlendshapeWeights = new Dictionary<int, float>();
        private Coroutine animationCoroutine;

        // Properties
        public bool IsPlaying => isPlaying;
        public float CurrentTime => currentAudioSource != null ? currentAudioSource.time : 0f;

        #region Unity Lifecycle

        private void Awake()
        {
            if (faceRenderer == null)
            {
                faceRenderer = GetComponent<SkinnedMeshRenderer>();
            }

            if (faceRenderer == null)
            {
                Debug.LogError("LipSyncController requires a SkinnedMeshRenderer!");
                enabled = false;
                return;
            }

            // Initialize weight dictionaries
            InitializeWeights();

            // Validate mappings
            ValidateMappings();
        }

        private void OnValidate()
        {
            if (faceRenderer != null)
            {
                ValidateMappings();
            }
        }

        #endregion

        #region Public API

        /// <summary>
        /// Play viseme timeline synchronized with audio
        /// </summary>
        public void PlayVisemeTimeline(List<VisemeFrame> timeline, AudioSource audioSource)
        {
            if (timeline == null || timeline.Count == 0)
            {
                Debug.LogWarning("Empty viseme timeline");
                return;
            }

            if (audioSource == null)
            {
                Debug.LogError("AudioSource is null");
                return;
            }

            // Stop current animation if playing
            Stop();

            // Set new timeline
            currentTimeline = timeline.OrderBy(v => v.timeMs).ToList(); // Ensure sorted by time
            currentAudioSource = audioSource;
            currentVisemeIndex = 0;

            // Start animation
            animationCoroutine = StartCoroutine(AnimateVisemes());

            if (showDebugInfo)
            {
                Debug.Log($"Started lip-sync with {timeline.Count} viseme frames, " +
                         $"duration: {timeline.Max(v => v.timeMs)}ms");
            }
        }

        /// <summary>
        /// Stop lip-sync animation
        /// </summary>
        public void Stop()
        {
            if (animationCoroutine != null)
            {
                StopCoroutine(animationCoroutine);
                animationCoroutine = null;
            }

            isPlaying = false;
            currentTimeline = null;
            currentAudioSource = null;
            currentVisemeIndex = 0;

            if (resetOnStop)
            {
                ResetMouth();
            }
        }

        /// <summary>
        /// Test a single viseme (for setup/debugging)
        /// </summary>
        public void TestViseme(string visemeId, float weight = 1.0f, float duration = 0.5f)
        {
            int blendshapeIndex = GetBlendshapeIndex(visemeId);
            if (blendshapeIndex >= 0)
            {
                StartCoroutine(TestVisemeCoroutine(blendshapeIndex, weight, duration));
            }
            else
            {
                Debug.LogWarning($"Viseme '{visemeId}' not mapped to any blendshape");
            }
        }

        /// <summary>
        /// Print all available blendshapes (for setup)
        /// </summary>
        [ContextMenu("Print All Blendshapes")]
        public void PrintAllBlendshapes()
        {
            if (faceRenderer == null || faceRenderer.sharedMesh == null)
            {
                Debug.LogError("No SkinnedMeshRenderer or mesh found");
                return;
            }

            Debug.Log($"=== Blendshapes in {faceRenderer.sharedMesh.name} ===");
            for (int i = 0; i < faceRenderer.sharedMesh.blendShapeCount; i++)
            {
                string shapeName = faceRenderer.sharedMesh.GetBlendShapeName(i);
                float currentWeight = faceRenderer.GetBlendShapeWeight(i);
                Debug.Log($"[{i}] {shapeName} (current weight: {currentWeight})");
            }
        }

        /// <summary>
        /// Reset all mouth blendshapes to neutral (weight 0)
        /// </summary>
        [ContextMenu("Reset Mouth")]
        public void ResetMouth()
        {
            foreach (var mapping in visemeMappings)
            {
                if (mapping.blendshapeIndex >= 0)
                {
                    faceRenderer.SetBlendShapeWeight(mapping.blendshapeIndex, 0f);
                    if (currentBlendshapeWeights.ContainsKey(mapping.blendshapeIndex))
                    {
                        currentBlendshapeWeights[mapping.blendshapeIndex] = 0f;
                    }
                    if (targetBlendshapeWeights.ContainsKey(mapping.blendshapeIndex))
                    {
                        targetBlendshapeWeights[mapping.blendshapeIndex] = 0f;
                    }
                }
            }
        }

        #endregion

        #region Animation

        private IEnumerator AnimateVisemes()
        {
            isPlaying = true;

            // Wait for audio to start playing
            while (currentAudioSource != null && !currentAudioSource.isPlaying)
            {
                yield return null;
            }

            if (currentAudioSource == null)
            {
                Stop();
                yield break;
            }

            // Animate visemes based on audio time
            while (isPlaying && currentAudioSource != null && currentAudioSource.isPlaying)
            {
                float currentTimeMs = currentAudioSource.time * 1000f;

                // Update target weights based on current time
                UpdateVisemeWeights(currentTimeMs);

                // Smoothly interpolate current weights toward target weights
                SmoothBlendshapeWeights();

                // Apply weights to blendshapes
                ApplyBlendshapeWeights();

                yield return null;
            }

            // Animation complete
            isPlaying = false;

            if (resetOnStop)
            {
                // Smoothly fade out to neutral
                yield return FadeToNeutral(0.2f);
            }

            if (showDebugInfo)
            {
                Debug.Log("Lip-sync animation completed");
            }
        }

        private void UpdateVisemeWeights(float currentTimeMs)
        {
            // Find the current and next viseme frames
            VisemeFrame currentViseme = null;
            VisemeFrame nextViseme = null;

            // Find current viseme (most recent frame before current time)
            for (int i = 0; i < currentTimeline.Count; i++)
            {
                if (currentTimeline[i].timeMs <= currentTimeMs)
                {
                    currentViseme = currentTimeline[i];
                    currentVisemeIndex = i;
                }
                else
                {
                    nextViseme = currentTimeline[i];
                    break;
                }
            }

            // Reset all target weights to 0
            var blendshapeIndices = visemeMappings
                .Where(m => m.blendshapeIndex >= 0)
                .Select(m => m.blendshapeIndex);

            foreach (var index in blendshapeIndices)
            {
                if (!targetBlendshapeWeights.ContainsKey(index))
                    targetBlendshapeWeights[index] = 0f;
                else
                    targetBlendshapeWeights[index] = 0f;
            }

            // Set target weight for current viseme
            if (currentViseme != null)
            {
                int blendshapeIndex = GetBlendshapeIndex(currentViseme.id);
                if (blendshapeIndex >= 0)
                {
                    float weight = currentViseme.weight *
                                 GetWeightMultiplier(currentViseme.id) *
                                 globalWeightMultiplier *
                                 maxBlendshapeWeight;

                    targetBlendshapeWeights[blendshapeIndex] = weight;

                    if (showDebugInfo && Time.frameCount % 30 == 0) // Log every 30 frames
                    {
                        Debug.Log($"Viseme: {currentViseme.id}, Weight: {weight:F1}, Time: {currentTimeMs:F0}ms");
                    }
                }
            }
        }

        private void SmoothBlendshapeWeights()
        {
            List<int> indices = targetBlendshapeWeights.Keys.ToList();

            foreach (int index in indices)
            {
                if (!currentBlendshapeWeights.ContainsKey(index))
                {
                    currentBlendshapeWeights[index] = 0f;
                }

                float target = targetBlendshapeWeights[index];
                float current = currentBlendshapeWeights[index];

                // Smooth interpolation
                float smoothed = Mathf.Lerp(current, target, Time.deltaTime * smoothingSpeed);
                currentBlendshapeWeights[index] = smoothed;
            }
        }

        private void ApplyBlendshapeWeights()
        {
            foreach (var kvp in currentBlendshapeWeights)
            {
                int index = kvp.Key;
                float weight = kvp.Value;

                if (index >= 0 && index < faceRenderer.sharedMesh.blendShapeCount)
                {
                    faceRenderer.SetBlendShapeWeight(index, weight);
                }
            }
        }

        private IEnumerator FadeToNeutral(float duration)
        {
            float elapsed = 0f;
            Dictionary<int, float> startWeights = new Dictionary<int, float>(currentBlendshapeWeights);

            while (elapsed < duration)
            {
                elapsed += Time.deltaTime;
                float t = elapsed / duration;

                foreach (var kvp in startWeights)
                {
                    int index = kvp.Key;
                    float startWeight = kvp.Value;
                    float weight = Mathf.Lerp(startWeight, 0f, t);
                    faceRenderer.SetBlendShapeWeight(index, weight);
                }

                yield return null;
            }

            // Ensure all weights are exactly 0
            foreach (var index in startWeights.Keys)
            {
                faceRenderer.SetBlendShapeWeight(index, 0f);
            }
        }

        private IEnumerator TestVisemeCoroutine(int blendshapeIndex, float weight, float duration)
        {
            // Ramp up
            float elapsed = 0f;
            float halfDuration = duration * 0.5f;

            while (elapsed < halfDuration)
            {
                elapsed += Time.deltaTime;
                float t = elapsed / halfDuration;
                faceRenderer.SetBlendShapeWeight(blendshapeIndex, Mathf.Lerp(0f, weight * maxBlendshapeWeight, t));
                yield return null;
            }

            // Ramp down
            elapsed = 0f;
            while (elapsed < halfDuration)
            {
                elapsed += Time.deltaTime;
                float t = elapsed / halfDuration;
                faceRenderer.SetBlendShapeWeight(blendshapeIndex, Mathf.Lerp(weight * maxBlendshapeWeight, 0f, t));
                yield return null;
            }

            faceRenderer.SetBlendShapeWeight(blendshapeIndex, 0f);
        }

        #endregion

        #region Helpers

        private void InitializeWeights()
        {
            targetBlendshapeWeights.Clear();
            currentBlendshapeWeights.Clear();

            foreach (var mapping in visemeMappings)
            {
                if (mapping.blendshapeIndex >= 0)
                {
                    targetBlendshapeWeights[mapping.blendshapeIndex] = 0f;
                    currentBlendshapeWeights[mapping.blendshapeIndex] = 0f;
                }
            }
        }

        private int GetBlendshapeIndex(string visemeId)
        {
            var mapping = visemeMappings.FirstOrDefault(m => m.visemeId == visemeId);
            return mapping?.blendshapeIndex ?? -1;
        }

        private float GetWeightMultiplier(string visemeId)
        {
            var mapping = visemeMappings.FirstOrDefault(m => m.visemeId == visemeId);
            return mapping?.weightMultiplier ?? 1.0f;
        }

        private void ValidateMappings()
        {
            if (faceRenderer == null || faceRenderer.sharedMesh == null) return;

            int blendshapeCount = faceRenderer.sharedMesh.blendShapeCount;

            foreach (var mapping in visemeMappings)
            {
                if (mapping.blendshapeIndex >= blendshapeCount)
                {
                    Debug.LogWarning($"Viseme '{mapping.visemeId}' mapped to invalid blendshape index " +
                                   $"{mapping.blendshapeIndex} (max: {blendshapeCount - 1})");
                }
            }
        }

        #endregion

        #region Debug

        private void OnGUI()
        {
            if (!showDebugInfo || !isPlaying) return;

            GUILayout.BeginArea(new Rect(10, 10, 300, 200));
            GUILayout.Label($"<b>Lip-Sync Debug</b>");
            GUILayout.Label($"Time: {CurrentTime:F2}s");
            GUILayout.Label($"Viseme Index: {currentVisemeIndex}/{currentTimeline?.Count ?? 0}");
            GUILayout.Label($"Active Blendshapes:");

            foreach (var kvp in currentBlendshapeWeights.Where(w => w.Value > 1f))
            {
                string name = faceRenderer.sharedMesh.GetBlendShapeName(kvp.Key);
                GUILayout.Label($"  [{kvp.Key}] {name}: {kvp.Value:F1}");
            }

            GUILayout.EndArea();
        }

        private void OnDrawGizmos()
        {
            if (!drawGizmos || !isPlaying || currentTimeline == null) return;

            // Draw timeline visualization
            // (Implementation left as exercise - could draw viseme timeline in Scene view)
        }

        #endregion
    }
}
