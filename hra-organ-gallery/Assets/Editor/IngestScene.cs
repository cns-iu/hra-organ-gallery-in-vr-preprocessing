using System.Collections;
using System.Collections.Generic;
using System.Linq;
using System.Runtime.Remoting.Messaging;
using Assets.Scripts.Scene;
using JetBrains.Annotations;
using log4net.Layout;
using UnityEditor;
using UnityEngine;
using System;
using UnityEngine.Rendering;
using System.Threading.Tasks;

namespace HRAOrganGallery
{
    /// <summary>
    /// A EditorWindow to load a scene from the HRA API and store it as a ScriptableObject
    /// </summary>
    public class IngestScene : EditorWindow
    {
        [Header("General")]
        private static string saveLocation = "Assets/ScriptableObjects";

        [Header("HRA API/scene")]
        private static string endpointApiScene = "https://apps.humanatlas.io/api--staging/v1/scene";
        private static string fileNameScene = "sceneAsset";
        private static SONodeArrayFromAPI sceneAsset;

        [Header("HRA API/organIris")]
        Dictionary<string, List<string>> sexOrganDict = new Dictionary<string, List<string>>();

        [Header("HRA API/refOrganScene")]
        private static string endpointApiRefOrgan = "https://apps.humanatlas.io/api--staging/v1/reference-organ-scene";
        private static string organQuery = "?organ-iri=";
        private static string sexQuery = "&sex=";
        private static string fileNameRefOrgan = "refOrganSceneAsset";

        /// <summary>
        /// A static method that is called when the corresponding menu emtry is selected
        /// </summary>
        [MenuItem("Tools/5. Update Scene/Fetch Assets from HRA API")]
        public static void ShowWindow()
        {
            GetWindow<IngestScene>("Ingest Scene and RefOrgan Scene from HRA API as Scriptable Objects");
        }

        private void OnGUI()
        {
            //instructions
            GUIStyle wordWrapStyle = new GUIStyle(EditorStyles.label);
            wordWrapStyle.wordWrap = true;
            EditorGUILayout.LabelField("To get the most recent <b>scene</b> and <b>refOrganScene</b> assets from the HRA API, click the three buttons below in sequence. When done, put the scene asset in the corresponding spot on the SceneSetup and all refOrganScene assets into the List on the OrganCaller.", wordWrapStyle);

            GUILayout.Label("General", EditorStyles.boldLabel);
            saveLocation = EditorGUILayout.TextField("Save to", saveLocation);

            GUILayout.Label("1. Get Scene from HRA API", EditorStyles.boldLabel);

            SceneConfiguration config = new SceneConfiguration();
            endpointApiScene = config.BuildUrl();

            endpointApiScene = EditorGUILayout.TextField("Scene API Endpoint", endpointApiScene);

            fileNameScene = EditorGUILayout.TextField("File name", fileNameScene);
            // sceneAsset = (SONodeArrayFromAPI)EditorGUILayout.ObjectField("Local scene asset", sceneAsset, typeof(ScriptableObject), false);

            if (GUILayout.Button("Fetch"))
            {
                SceneLoader sceneLoader = new SceneLoader();
                CallAPI(sceneLoader, endpointApiScene, fileNameScene);
            }

            GUILayout.Label("2. Get updated listing of all organ IRIs with sex from HRA API", EditorStyles.boldLabel);

            if (GUILayout.Button("Compile listing"))
            {

                string assetPath = $"{saveLocation}/{fileNameScene}.asset";
                SONodeArrayFromAPI asset = AssetDatabase.LoadAssetAtPath<SONodeArrayFromAPI>(assetPath);

                if (asset != null)
                {
                    Debug.Log("Loaded asset: " + asset.name);
                    sexOrganDict = GetListing(asset);
                }
                else
                {
                    Debug.LogError("Failed to load asset.");
                }
            }

            GUILayout.Label("3. Get RefOrgan Scene from HRA API", EditorStyles.boldLabel);

            endpointApiRefOrgan = EditorGUILayout.TextField("RefOrgan Scene API Endpoint (Base)", endpointApiRefOrgan);
            organQuery = EditorGUILayout.TextField("Query string key (organ IRI)", organQuery);
            sexQuery = EditorGUILayout.TextField("Query string key (sex)", sexQuery);
            fileNameRefOrgan = EditorGUILayout.TextField("File name ref organ", fileNameRefOrgan);

            if (GUILayout.Button("Fetch"))
            {
                Debug.Log("Fetching");
                _ = FetchWithDelayAsync();
            }

            GUILayout.Label("4. Point OrganCaller to refOrganAssets", EditorStyles.boldLabel);
            EditorGUILayout.LabelField("When done with fetching refOrganAssets, put the scene asset in the corresponding spot on the SceneSetup and all refOrganScene assets into the List on the OrganCaller.", wordWrapStyle);
        }

        private async Task FetchWithDelayAsync()
        {
            HighResOrganLoader loader = new HighResOrganLoader();
            SceneLoader l = new SceneLoader();
            string url = "";

            foreach (var kvp in sexOrganDict)
            {
                foreach (var v in kvp.Value)
                {
                    url = endpointApiRefOrgan + organQuery + v + sexQuery + kvp.Key.ToLower();
                    string extension = v.Split("/").Last();
                    Debug.Log($"Now calling {url}");

                    CallAPI(l, url, $"{fileNameRefOrgan}_{extension}_{kvp.Key.ToLower()}");

                    // Wait for seconds before the next API call
                    await Task.Delay(10000);
                }
            }
        }

            /// <summary>
            /// Get dict of all sex and organ IRI conbinations
            /// </summary>
            /// <param name="asset"></param>
        private Dictionary<string, List<string>> GetListing(SONodeArrayFromAPI asset)
        {
            Dictionary<string, List<string>> result = new Dictionary<string, List<string>>();
            for (int i = 0; i < asset.nodes.Length; i++)
            {

                Node current = asset.nodes[i];
                //disregard tissue blocks
                if (current.sex == null)
                {
                    continue;
                }
                else
                {
                    if (result.TryGetValue(current.sex, out List<string> valueList))
                    {
                        valueList.Add(current.representation_of);
                    }
                    else
                    {
                        result[current.sex] = new List<string> { current.representation_of };
                    }
                }
            }

            result.Remove("");

            foreach (var kvp in result)
            {
                Debug.Log($"{kvp.Key} has {kvp.Value.Count} values.");
            }

            return result;
        }

        /// <summary>
        /// Uses the provided IApiResponseHandler and calls the provided URL with it
        /// </summary>
        /// <param name="handler"></param>
        /// <param name="endpoint"></param>
        private async void CallAPI(IApiResponseHandler<NodeArray> handler, string endpoint, string name)
        {
            NodeArray nodeArray = await handler.ShareData(endpoint);
            SaveToScriptableObject(nodeArray, name);
        }

        private SONodeArrayFromAPI SaveToScriptableObject(NodeArray nodeArrayFromWeb, string name)
        {
            //create new ScriptableObject
            SONodeArrayFromAPI saveAsset = ScriptableObject.CreateInstance<SONodeArrayFromAPI>();

            //create List to hold nodes temporarily
            List<Node> nodesAsList = new List<Node>();

            //lop through NodeArrayFromWeb and initialize Nodes from it
            for (int i = 0; i < nodeArrayFromWeb.nodes.Length; i++)
            {
                Node current = nodeArrayFromWeb.nodes[i];
                nodesAsList.Add(current);
            }

            //assign List to nodes array
            saveAsset.nodes = nodesAsList.ToArray();

            // create and save asset            
            AssetDatabase.CreateAsset(saveAsset, $"{saveLocation}/{name}.asset");
            // Debug.Log($"{saveAsset} saved to {saveLocation}/{name}.asset");
            AssetDatabase.SaveAssets();

            return saveAsset;
        }
    }
}
