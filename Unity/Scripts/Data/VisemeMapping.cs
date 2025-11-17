using System;
using System.Collections.Generic;
using UnityEngine;

namespace VoiceAgent.Data
{
    /// <summary>
    /// Mapping between Rhubarb viseme IDs and Unity blendshape indices
    /// </summary>
    [Serializable]
    public class VisemeBlendshapeMapping
    {
        [Tooltip("Viseme ID (A, B, C, D, E, F, G, H, X)")]
        public string visemeId;

        [Tooltip("Blendshape index in SkinnedMeshRenderer")]
        public int blendshapeIndex = -1;

        [Tooltip("Weight multiplier for this viseme (default 1.0)")]
        [Range(0f, 2f)]
        public float weightMultiplier = 1.0f;
    }

    /// <summary>
    /// Scriptable object for storing viseme mappings (optional, can use inspector array)
    /// </summary>
    [CreateAssetMenu(fileName = "VisemeMapping", menuName = "Voice Agent/Viseme Mapping")]
    public class VisemeMappingAsset : ScriptableObject
    {
        [Header("Rhubarb Viseme to Blendshape Mapping")]
        [Tooltip("Map each Rhubarb viseme to a blendshape index")]
        public List<VisemeBlendshapeMapping> mappings = new List<VisemeBlendshapeMapping>
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

        /// <summary>
        /// Get blendshape index for viseme ID
        /// </summary>
        public int GetBlendshapeIndex(string visemeId)
        {
            foreach (var mapping in mappings)
            {
                if (mapping.visemeId == visemeId)
                    return mapping.blendshapeIndex;
            }
            return -1;
        }

        /// <summary>
        /// Get weight multiplier for viseme ID
        /// </summary>
        public float GetWeightMultiplier(string visemeId)
        {
            foreach (var mapping in mappings)
            {
                if (mapping.visemeId == visemeId)
                    return mapping.weightMultiplier;
            }
            return 1.0f;
        }

        /// <summary>
        /// Print all blendshape names from a SkinnedMeshRenderer (for setup help)
        /// </summary>
        public static void PrintBlendshapes(SkinnedMeshRenderer renderer)
        {
            if (renderer == null || renderer.sharedMesh == null)
            {
                Debug.LogWarning("No SkinnedMeshRenderer or mesh found");
                return;
            }

            Debug.Log($"=== Blendshapes in {renderer.sharedMesh.name} ===");
            for (int i = 0; i < renderer.sharedMesh.blendShapeCount; i++)
            {
                string shapeName = renderer.sharedMesh.GetBlendShapeName(i);
                Debug.Log($"[{i}] {shapeName}");
            }
        }
    }
}
