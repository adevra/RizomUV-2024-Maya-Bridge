![ssbridge.png](https://i.postimg.cc/YSXwpyTK/ssbridge.png)

# RizomUV 2024 Bridge for Maya

Initially started as an update for the Official Origami Digital Maya 2018 Bridge by Oliver Hotz, turned out to be a major re-write, The RizomUV 2024 Bridge for Maya provides a seamless workflow between Autodesk Maya and RizomUV, allowing users to easily transfer UV data for advanced UV unwrapping and packing. 


## New Features

- **Drag-and-Drop Installer**: Installer script will handle everything. 
- **Namespace Handling**: Ensures that imported objects are correctly namespaced, avoiding multiple namespace entries upon each transfer.
- **Material Assignment Preservation**: Maintains original material assignments after UV data is transferred back to Maya.
- **Modern UI**: Script UI now matches the RizomUV 2024 colors

## Repository Structure

This repository includes support for both Python 2 and Python 3 versions of Maya:

- `/RizomUV Bridge 2024/`: Scripts for Maya versions using Python 3.
- `/RizomUV Bridge 2024 py2/`: Scripts for Maya versions using Python 2.

## Installation

1. **Download the Repository**: Download the repository from Github.
2. **Choose the Correct Folder**: Navigate to the folder corresponding to your Maya Python version **(use py2 for Maya versions below 2022)**.
3. **Drag-and-Drop Installer**: Locate the **drag_and_drop_install.py** script within the chosen folder.
Drag and drop this file into the Maya viewport. Installer will prompt with a file browser to select RizomUV executable, (most likely inside C:\Program Files\Rizom Lab\...)
it will then, add a shelf button under the currently active shelf. 

## Usage

Open the Script UI: 
After installation, a new shelf button will be available in Maya. Click this button to open the RizomUV 2024 Bridge UI.

Send Selected Geometry to RizomUV:
Select meshes in Maya.
In the RizomUV 2024 Bridge UI, click the **Send Selected** button.
Optionally, check Transfer Existing UVs to Rizom if you want to include the existing UVs in the transfer.

Get UVs from RizomUV:
After editing UVs in RizomUV simply CTRL+S and save that file. 
Go back to Maya viewport and select the meshes you want to replace their UVs and click the **Get UVs** button.
Optionally, check Long Line Fix if you want to remove long lines from the imported UV data.

Instant UVs:
Use the Instant UVs button for an automated roundtrip workflow, sending the selected geometry to RizomUV, processing the UVs, and importing them back into Maya with one click.

## License
This project is licensed under the MIT License. See the LICENSE file for details.

## Contributing
Contributions are welcome! Please fork the repository and submit pull requests for any enhancements or bug fixes.

## Support
For any issues or questions, please open an issue on the GitHub repository.
