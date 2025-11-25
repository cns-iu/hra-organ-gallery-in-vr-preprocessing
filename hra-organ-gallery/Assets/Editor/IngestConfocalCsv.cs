using System.Collections.Generic;
using UnityEngine;
using UnityEditor;

namespace HRAOrganGallery
{

    public class IngestConfocalCsv : EditorWindow
    {
        //fill in the file name here
        private static string fileName = "F8iic-quantificationV3";

        //decrease to read in **more** rows from the cell position CSV file
        private static int readIterator = 1;

        private static string sourceFolder = "Assets/Resources/Wong";

        private static string savedAssetFolder = "Assets/Resources/Wong";
        private static string saveAs = $"{fileName}";

        private string
            description =
                "Ingest a list of cells with columns for different biomarkers.";

        [MenuItem("Tools/4. Ingest Confocal CSV")]
        private static void ShowWindow()
        {
            //set up window
            var window = GetWindow<IngestConfocalCsv>();
            window.titleContent = new GUIContent("Ingest Confocal CSV");
            window.Show();
        }

        private void OnGUI()
        {
            GUILayout.Label("Read CSV", EditorStyles.boldLabel);

            // Display the description with word wrapping
            EditorGUILayout
                .LabelField(description);

            fileName = EditorGUILayout.TextField("Source File Name", fileName);
            sourceFolder = EditorGUILayout.TextField("Source Folder", sourceFolder);
            savedAssetFolder = EditorGUILayout.TextField("Save to Folder", savedAssetFolder);
            saveAs = EditorGUILayout.TextField("Save as", saveAs);

            //not super elegant and safe yet --needs fix
            readIterator = int.Parse(EditorGUILayout.TextField("Read Iterator", readIterator.ToString()));

            if (GUILayout.Button("Transform to Scriptable Object"))
            {
                CreateInstance();
            }
        }

        private void CreateInstance()
        {
            // instantiate
            SOConfocalDataset instance = ScriptableObject.CreateInstance<SOConfocalDataset>();

            List<RowConfocal> rows = CSVReader.ReadCsv($"Assets/Resources/Wong/{fileName}.csv");

            //initialize counter
            int counter = 0;

            // Set values
            rows.ForEach(
                r =>
                {
                    if (counter % readIterator == 0)
                    {
                        instance.rows.Add(r);
                    }
                    counter++;
                }
            );

            Debug.Log($"Read in {instance.rows.Count} rows into {saveAs}.");

            // save as asset
            AssetDatabase.CreateAsset(instance, $"{savedAssetFolder}/{saveAs}.asset");
            AssetDatabase.SaveAssets();

            Debug.Log($"ScriptableObject created and saved at {savedAssetFolder}/{saveAs}.asset");
        }
    }



}
