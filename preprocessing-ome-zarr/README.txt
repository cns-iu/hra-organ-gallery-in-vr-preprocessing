Rough Notes on OME-ZARR data store import (to be furnished)
Dabbled with using Google cloud API commands via GIT BASH, but was unable to do so because I did not have necessary wget packages, and pivoted to using python, because it is more universal.

Initial Approach using RAW and JSON files
First python script involving python packages for ZARR handling did not work because the Vitesse data uses DirectoryStore method, while the current python API uses both local and remote storage. Hence, rewrote the script to workaround that.
Wrote a tryout script that handles both local and remote data stores for future ZARR purposes, that uses “python download_zarr_tryout.py source_url.zarr destination_local_folder.zarr” instead of “python download_zarr.py” and stored it in “test” folder.
ZARR data was extracted as such and put into Unity/Assets/StreamingAssets/ so as to not corrupt/ignore chunk metadata. It is specifically used for unknown data types.
mcmicro_io.zarr/
  images/
  labels/
  table/
  .zgroup
Next, I performed an inspection of the data to find out what is the smallest volume/channel/data type it is, using a separate python script. I found out the data reference Yash J. gave me was 2D data, which we have already implemented. I started searching for 3D ZARR data.
I settled on using this data: Blin et al., PLoS Biol 2019 since it was the only one labelled “3D” and “zarr” in the examples. 
I created a new python script called “inspect_remote.py” to ascertain that the data in the provided url was fit for rendering in Unity as a 3D volume, and found out:
shape: (2, 236, 275, 271) means the image data is a real 3D volume with 2 channels, and the most likely axis order is: (channel, z, y, x)
So this dataset is suitable for a true Unity Texture3D workflow, not a fake channel-stack workaround, that I was trying with earlier 2D data. 
Used the “export_volume.py” script to get the ZARR volume in my local storage, and thereafter transferred to “StreamingAssets” folder for Unity
Used a 3D cube to render raw and json files on them facilitated by a “VolumeLoader.cs script”. Even though it only rendered flat images on the cubes surface, it goes to show that our data actually produces something.
I tried multiple approaches using raw and json data, but was not able to get an appropriate 3D render. Either the FPS was too low, or the render was not the same as on the website. This approach was scrapped.



VOXEL CLOUD APPROACH:
Prototyped direct OME-Zarr ingestion from an IDR microscopy dataset and validated extraction of multichannel volumetric data using a python script “export_omezarr_to_local.py”
Built a custom Unity Editor ingestion pipeline that converts exported microscopy volumes into native Texture3D assets and generates reusable dataset assets. 
Implemented a GPU-based volume rendering system in Unity using: a custom HLSL raymarch shader, runtime multi-channel compositing, cube-based volumetric rendering bounds
Implemented simultaneous rendering of multiple microscopy channels, similar to Vitessce-style microscopy visualization workflows. 
Resolved major rendering issues including: inside-volume visibility, excessive smoothing/blurriness, anisotropic voxel distortion
Added interactions such as Grab and Scale to the ZARR Volume render.
Adjusted shader to work with URP 
LIMITATIONS: Render looks beautiful and encompasses both the channels in each level accurately in one with true point distribution using custom voxel render, but cannot be used in URP projects, such as the HRA organ gallery.



Unlit URP shader approach using slices of data
New python exporter that remotely uses url to create slices of the channels from highest resolution level, instead of obtaining JSON and RAW files like before.
Slices are imported into Unity, and the following settings are applied:
Select all PNGs. Set: Texture Type → Default; sRGB → OFF; Alpha Source → None; Generate Mipmaps → OFF; Filter Mode → Point; Wrap Mode → Clamp ; Apply.
Next, I tried to render a single slice in the scene, using a URP/Unlit material, with following properties: Surface Type → Transparent; Blending Mode →  Alpha; Render Face → Both; Base Map → slice PNG and obtained a render of the slice.
Wrote a script “SliceStackGenerator.cs” that uses a URP/Unlit shader to generate a stack of slices that form a volumetric cube. Material has to be transparent with additive alpha.
Amended script to allow step size and billboard towards the user so that the render doesn’t become invisible from the sides. Cancelled this approach because it was incorrect.
Decided to use axial and cross stacks of the same data, to bypass the problem of the planes becoming invisible from the sides.
Doing this for all three axes to address the same issue for top and bottom view.
