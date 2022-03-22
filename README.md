# DeepArc 3D Slicer Timeline extension

[![DOI](https://zenodo.org/badge/472784685.svg)](https://zenodo.org/badge/latestdoi/472784685)

## Development setup

### Environment

1. Clone [this project](https://github.com/DLR-SC/slicer-timeline).
1. Install [3D Slicer](https://download.slicer.org/).
1. Run 3D Slicer.
1. In 3D Slicer, select the `Developer Tools > Extension Wizard` module from the module list in the top left. 
1. Click `Select Extension` on the left.
1. Browse and select the folder where you cloned this project (e. g. `slicer-timeline`).
1. Make sure that all modules as well as `Add selected module to search paths` are selected and click `Yes`.
1. You can now select the `DeepArc Timeline` module from the module list in the top left (either from the top level or via
   `Sequences > DeepArc Timeline`).

### Editor

#### PyCharm

##### Code completion

For PyCharm to recognize (most of) the 3D Slicer Python modules to provide IntelliSense, 3D Slicer's custom
`PythonSlicer` Python interpreter has to be selected as the Python interpreter for the project:

1. Open the folder where you cloned this project as a project in PyCharm.
1. Open the settings (`CTRL + ALT + S` on Windows and Linux or via `File > Settings...` in the menu bar).
1. Select `Project: 'project name' > Python Interpreter`.
1. In the top right, click on the cog wheel icon and select `Add...`
1. Select `System Interpreter`.
1. Set the `Interpreter:` field by clicking on the three dots in the top right and browsing to your 3D Slicer
   installation directory. Select the `bin` folder and, finally, select `PythonSlicer`. Be careful not to select
   `SlicerPython` here!
1. Click `OK` in the `Add Python Interpreter` window.
1. Click `OK` in the `Settings` window.

##### Debugging assistance

**This feature is only available in PyCharm Professional**

Refer to the respective section in the README of the DebuggingTools Extension:
[Link](https://github.com/SlicerRt/SlicerDebuggingTools#instructions-for-pycharm)
