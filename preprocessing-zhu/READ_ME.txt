process-zhu-data-z-offset.ipynb is only for when all 28 layers are being visualized in Unity at once. Make note that the z-offset needs to be adjusted and readjusted based off the model/visualization scaling in Unity. 

generated_cell_type_complete_crosswalk.csv was provided by Yashwardhan Jain to be used to aggregate cell types to broader cell types, so that we have colours for every data point (cell type)

process-zhu-aggregate.ipynb is for sorting layer and xenium rna data into top 5 cell types/biomarkers(labelled cell types for convenience with python notebook and unity) and others, and aggregating all others into a single type "Other"