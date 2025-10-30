using System.Collections.Generic;
using System.Globalization;
using System.IO;
using System.Net;
using CsvHelper;
using UnityEditor;
using UnityEngine;

/// <summary>
/// Unified editor window to download and transform cell population data
/// </summary>
public class CellPopulationDataManager : EditorWindow
{
    // Anatomical Structures URLs and Paths
    private string asDownloadUrl = "https://grlc.io/api-git/hubmapconsortium/ccf-grlc/subdir/hra-pop//cell_types_in_anatomical_structurescts_per_as.csv";
    private string asCsvSavePath = "Assets/Resources/as-ct-hra-pop.csv";
    private string asCsvPath = "Assets/Resources/as-ct-hra-pop.csv";
    private string asSoPath = "Assets/ScriptableObjects";
    private string asSoName = "AsCellSummaries";

    // Extraction Site URLs and Paths
    private string esDownloadUrl = "https://grlc.io/api-git/hubmapconsortium/ccf-grlc/subdir/hra-pop//cell-types-per-extraction-site.csv";
    private string esCsvSavePath = "Assets/Resources/es-ct-hra-pop.csv";
    private string esCsvPath = "Assets/Resources/es-ct-hra-pop.csv";
    private string esSoPath = "Assets/ScriptableObjects";
    private string esSoName = "EsCellSummaries";

    private Vector2 scrollPosition;

    [MenuItem("Tools/1. Visualize hra-pop Data/1. Download and Serialize data")]
    public static void ShowWindow()
    {
        GetWindow<CellPopulationDataManager>("Cell Population Data Manager");
    }

private void OnGUI()
{
    scrollPosition = EditorGUILayout.BeginScrollView(scrollPosition);

    GUILayout.Label("HRA Cell Population Data Manager", EditorStyles.boldLabel);
    EditorGUILayout.HelpBox("This tool downloads cell population CSVs from the HRA API and transforms them into ScriptableObjects for use in the VR application.", MessageType.Info);
    EditorGUILayout.Space();

    // ===== ANATOMICAL STRUCTURE (AS) =====
    //DrawSeparator();
    GUILayout.Label("ANATOMICAL STRUCTURE (AS)", EditorStyles.boldLabel);
    DrawSeparator();

    EditorGUILayout.LabelField("Download Settings", EditorStyles.boldLabel);
    EditorGUILayout.HelpBox("Downloads cell type data organized by anatomical structures (organs, tissues).", MessageType.None);
    asDownloadUrl = EditorGUILayout.TextField("AS Download URL", asDownloadUrl);
    asCsvSavePath = EditorGUILayout.TextField("CSV Save Path", asCsvSavePath);
    
    if (GUILayout.Button("Download CSV", GUILayout.Height(30)))
    {
        DownloadCSV(asDownloadUrl, asCsvSavePath, "AS");
    }

    EditorGUILayout.Space();
    EditorGUILayout.LabelField("Transform Settings", EditorStyles.boldLabel);
    EditorGUILayout.HelpBox("Converts the downloaded CSV into an editable ScriptableObject asset.", MessageType.None);
    asCsvPath = EditorGUILayout.TextField("CSV Path", asCsvPath);
    asSoPath = EditorGUILayout.TextField("ScriptableObject Path", asSoPath);
    asSoName = EditorGUILayout.TextField("ScriptableObject Name", asSoName);

    if (GUILayout.Button("Transform to ScriptableObject", GUILayout.Height(30)))
    {
        TransformAsToScriptableObject(asCsvPath, asSoPath, asSoName);
    }

    EditorGUILayout.Space(20);

    // ===== EXTRACTION SITE (ES) =====
    //DrawSeparator();
    GUILayout.Label("EXTRACTION SITE (ES)", EditorStyles.boldLabel);
    DrawSeparator();

    EditorGUILayout.LabelField("Download Settings", EditorStyles.boldLabel);
    EditorGUILayout.HelpBox("Downloads cell type data organized by tissue extraction sites (specific donor samples).", MessageType.None);
    esDownloadUrl = EditorGUILayout.TextField("ES Download URL", esDownloadUrl);
    esCsvSavePath = EditorGUILayout.TextField("CSV Save Path", esCsvSavePath);

    if (GUILayout.Button("Download CSV", GUILayout.Height(30)))
    {
        DownloadCSV(esDownloadUrl, esCsvSavePath, "ES");
    }

    EditorGUILayout.Space();
    EditorGUILayout.LabelField("Transform Settings", EditorStyles.boldLabel);
    EditorGUILayout.HelpBox("Converts the downloaded CSV into an editable ScriptableObject asset.", MessageType.None);
    esCsvPath = EditorGUILayout.TextField("CSV Path", esCsvPath);
    esSoPath = EditorGUILayout.TextField("ScriptableObject Path", esSoPath);
    esSoName = EditorGUILayout.TextField("ScriptableObject Name", esSoName);

    if (GUILayout.Button("Transform to ScriptableObject", GUILayout.Height(30)))
    {
        TransformEsToScriptableObject(esCsvPath, esSoPath, esSoName);
    }


    EditorGUILayout.EndScrollView();
}

    private void DrawSeparator()
    {
        EditorGUILayout.LabelField("", GUI.skin.horizontalSlider);
    }

    // ===== DOWNLOAD LOGIC =====
    private void DownloadCSV(string url, string savePath, string dataType)
    {
        using (WebClient client = new WebClient())
        {
            try
            {
                client.Headers.Add("User-Agent", "UnityEditor");
                client.Headers.Add("Accept", "text/csv");

                Debug.Log($"Downloading {dataType} CSV from: {url}");

                string csvData = client.DownloadString(url);

                // Create directory if it doesn't exist
                string directory = Path.GetDirectoryName(savePath);
                if (!Directory.Exists(directory))
                {
                    Directory.CreateDirectory(directory);
                }

                File.WriteAllText(savePath, csvData);
                AssetDatabase.Refresh();

                Debug.Log($"✓ {dataType} CSV downloaded and saved to: {savePath}");
            }
            catch (WebException webEx)
            {
                var response = (HttpWebResponse)webEx.Response;
                if (response != null)
                {
                    Debug.LogError($"HTTP Status Code: {response.StatusCode}");
                    using (var reader = new StreamReader(response.GetResponseStream()))
                    {
                        Debug.LogError("Response: " + reader.ReadToEnd());
                    }
                }
                else
                {
                    Debug.LogError($"Failed to download {dataType} CSV: {webEx.Message}");
                }
            }
            catch (IOException ioEx)
            {
                Debug.LogError($"Failed to save {dataType} CSV: {ioEx.Message}");
            }
        }
    }

    // ===== TRANSFORM AS LOGIC =====
    private void TransformAsToScriptableObject(string csvPath, string soPath, string soName)
    {
        SOHraApiAsCellSummaries list = ScriptableObject.CreateInstance<SOHraApiAsCellSummaries>();

        if (!File.Exists(csvPath))
        {
            Debug.LogError($"AS CSV file not found at path: {csvPath}");
            return;
        }

        using (var reader = new StreamReader(csvPath))
        using (var csv = new CsvReader(reader, CultureInfo.InvariantCulture))
        {
            csv.Read();
            csv.ReadHeader();

            while (csv.Read())
            {
                var row = new CellSummaryRow
                {
                    organ = csv.GetField<string>("organ"),
                    asId = csv.GetField<string>("as"),
                    asLabel = csv.GetField<string>("as_label"),
                    sex = csv.GetField<string>("sex"),
                    tool = csv.GetField<string>("tool"),
                    modality = csv.GetField<string>("modality"),
                    cellId = csv.GetField<string>("cell_id"),
                    cellLabel = csv.GetField<string>("cell_label"),
                    cellCount = csv.GetField<float>("cell_count"),
                    cellPercentage = csv.GetField<float>("cell_percentage"),
                    datasetCount = csv.GetField<int>("dataset_count")
                };

                list.rows.Add(row);
            }
        }

        // Create directory if it doesn't exist
        if (!Directory.Exists(soPath))
        {
            Directory.CreateDirectory(soPath);
        }

        string fullPath = $"{soPath}/{soName}.asset";
        AssetDatabase.CreateAsset(list, fullPath);
        AssetDatabase.SaveAssets();

        Debug.Log($"✓ AS ScriptableObject created with {list.rows.Count} rows at: {fullPath}");
    }

    // ===== TRANSFORM ES LOGIC =====
    private void TransformEsToScriptableObject(string csvPath, string soPath, string soName)
    {
        SOHraApiEsCellSummaries list = ScriptableObject.CreateInstance<SOHraApiEsCellSummaries>();

        if (!File.Exists(csvPath))
        {
            Debug.LogError($"ES CSV file not found at path: {csvPath}");
            return;
        }

        using (var reader = new StreamReader(csvPath))
        using (var csv = new CsvReader(reader, CultureInfo.InvariantCulture))
        {
            csv.Read();
            csv.ReadHeader();

            while (csv.Read())
            {
                var row = new ExtractionSiteSummaryRow
                {
                    organId = csv.GetField<string>("organ_id"),
                    organ = csv.GetField<string>("organ"),
                    extractionSite = csv.GetField<string>("extraction_site"),
                    sex = csv.GetField<string>("sex"),
                    tool = csv.GetField<string>("tool"),
                    modality = csv.GetField<string>("modality"),
                    cellId = csv.GetField<string>("cell_id"),
                    cellLabel = csv.GetField<string>("cell_label"),
                    cellCount = csv.GetField<float>("cell_count"),
                    cellPercentage = csv.GetField<float>("cell_percentage")
                };

                list.rows.Add(row);
            }
        }

        // Create directory if it doesn't exist
        if (!Directory.Exists(soPath))
        {
            Directory.CreateDirectory(soPath);
        }

        string fullPath = $"{soPath}/{soName}.asset";
        AssetDatabase.CreateAsset(list, fullPath);
        AssetDatabase.SaveAssets();

        Debug.Log($"✓ ES ScriptableObject created with {list.rows.Count} rows at: {fullPath}");
    }
}