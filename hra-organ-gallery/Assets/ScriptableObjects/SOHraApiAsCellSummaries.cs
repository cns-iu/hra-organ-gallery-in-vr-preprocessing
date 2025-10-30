using System;
using System.Collections.Generic;
using Unity.VisualScripting;
using UnityEngine;
using UnityEngine.Scripting;

// ==================== ANATOMICAL STRUCTURE (AS) CLASSES ====================

[Serializable]
/// <summary>
/// A Scriptable Object to capture a CSV file with cell summaries for anatomical structres from hra-pop
/// </summary>
public class SOHraApiAsCellSummaries : ScriptableObject
{
    public List<CellSummaryRow> rows = new List<CellSummaryRow>();	
}

[Serializable]
/// <summary>
/// A helper class modeling a row in a CSV for cell summaries for anatomical structures
/// </summary>
public class CellSummaryRow
{
	[field: Serialize] public string organ, asId, asLabel, sex, tool, modality, cellId, cellLabel;
	[field: Serialize] public float cellCount, cellPercentage;
	[field: Serialize] public int datasetCount;
 }


// ==================== EXTRACTION SITE (ES) CLASSES ====================

[Serializable]
/// <summary>
/// A Scriptable Object to capture a CSV file with cell summaries for extraction sites from hra-pop
/// </summary>
public class SOHraApiEsCellSummaries : ScriptableObject
{
    public List<ExtractionSiteSummaryRow> rows = new List<ExtractionSiteSummaryRow>();
}

[Serializable]
/// <summary>
/// A helper class modeling a row in a CSV for cell summaries for extraction sites
/// </summary>
public class ExtractionSiteSummaryRow
{
    [field: Serialize] public string organId, organ, extractionSite, sex, tool, modality, cellId, cellLabel;
    [field: Serialize] public float cellCount, cellPercentage;
}