import math
import traceback
from typing import Optional, List

import qt
import slicer
from MRMLCorePython import (
    vtkMRMLScriptedModuleNode,
    vtkMRMLScene,
    vtkMRMLSliceNode,
)
from MRMLLogicPython import vtkMRMLSliceLogic
from slicer.ScriptedLoadableModule import (
    ScriptedLoadableModule,
    ScriptedLoadableModuleLogic,
    ScriptedLoadableModuleTest,
    ScriptedLoadableModuleWidget,
)
from vtkSlicerSequencesModuleMRMLPython import vtkMRMLSequenceBrowserNode
from vtkmodules.vtkCommonKitPython import vtkCommand


class DeepArcTimeline(ScriptedLoadableModule):
    def __init__(self, parent):
        ScriptedLoadableModule.__init__(self, parent)

        self.parent.title = "DeepArc Timeline"
        self.parent.categories = ["", "Sequences"]
        self.parent.dependencies = []
        self.parent.contributors = [
            "Wadim Koslow (Deutsches Zentrum für Luft- und Raumfahrt e.V.)",
            "Philipp Rosauer (Deutsches Zentrum für Luft- und Raumfahrt e.V.)",
            "David Knapp (Deutsches Zentrum für Luft- und Raumfahrt e.V.)",
            "Jonas Levin Weber (Deutsches Zentrum für Luft- und Raumfahrt e.V.)",
        ]
        self.parent.helpText = "This is the DeepArc Timeline extension for 3D Slicer."
        self.parent.acknowledgementText = ""

    def setup(self):
        """
        This method is called when this extension is loaded (e.g. when Slicer is started
        and the extension is added to the search path for extensions)
        """
        pass


class DeepArcTimelineWidget(
    ScriptedLoadableModuleWidget, slicer.util.VTKObservationMixin
):
    INPUT_SLICE = "InputSlice"
    INPUT_SEQUENCE_BROWSER = "InputSequenceBrowser"

    def __init__(self, parent=None):
        """
        Called when the user opens the module the first time and the widget is
        initialized.
        """
        ScriptedLoadableModuleWidget.__init__(self, parent)

        # This is needed for parameter node observation.
        slicer.util.VTKObservationMixin.__init__(self)

        self.logic: Optional[DeepArcTimelineLogic] = None

        # This object has no real type that can be hinted. The object is a mere
        # collection of references to the child widgets of this widget.
        self.ui = None

        self.mrml_node_widgets = None

        self.timeline_widget: Optional[TimelineWidget] = None

        self.parameter_node: Optional[vtkMRMLScriptedModuleNode] = None
        self.updating_gui_from_parameter_node = False

    def setup(self):
        """
        Called when the user opens the module the first time and the widget is
        initialized.
        """
        ScriptedLoadableModuleWidget.setup(self)

        # Load widget from .ui file (created by Qt Designer). Additional widgets can be
        # instantiated manually and added to self.layout.
        ui_widget = slicer.util.loadUI(self.resourcePath("UI/DeepArcTimeline.ui"))
        self.layout.addWidget(ui_widget)
        self.ui = slicer.util.childWidgetVariables(ui_widget)

        # A dictionary that matches unique keys to the MRML node widgets contained in
        # DeepArcTimeline's GUI.
        self.mrml_node_widgets = {
            self.INPUT_SLICE: self.ui.slice_selector,
            self.INPUT_SEQUENCE_BROWSER: self.ui.sequence_browser_selector,
        }

        # Set the scene in MRML widgets. Make sure that in Qt designer the top-level
        # qMRMLWidget's "mrmlSceneChanged(vtkMRMLScene*)" signal is connected to each
        # MRML widget's "setMRMLScene(vtkMRMLScene*)" slot.
        ui_widget.setMRMLScene(slicer.mrmlScene)

        # Load additional widgets
        self.timeline_widget = TimelineWidget()
        slicer.util.mainWindow().addDockWidget(
            qt.Qt.BottomDockWidgetArea, self.timeline_widget
        )

        # Create the logic class. Logic implements all computations that should be
        # possible to run in batch mode, without a graphical user interface.
        self.logic = DeepArcTimelineLogic()

        # These connections ensure that we update the parameter node when the scene is
        # closed.
        self.addObserver(
            slicer.mrmlScene,
            slicer.mrmlScene.StartCloseEvent,
            self.on_scene_start_close,
        )
        self.addObserver(
            slicer.mrmlScene,
            slicer.mrmlScene.EndCloseEvent,
            self.on_scene_end_close,
        )

        # These connections ensure that whenever the user changes some settings on the
        # GUI, that is saved in the MRML scene (in the selected parameter node).
        for ref_name, widget in self.mrml_node_widgets.items():
            widget.connect(
                "currentNodeChanged(vtkMRMLNode*)",
                self.update_parameter_node_from_gui,
            )

        # Connect signals
        self.timeline_widget.progressUpdate.connect(self.ui.progress_bar.setValue)
        self.ui.btn_load.connect("clicked()", self.load_timeline)
        self.ui.btn_toggle_timeline.connect(
            "clicked()",
            self.btn_toggle_timeline_clicked,
        )

        # Make sure the parameter node is initialized (needed for module reload).
        self.initialize_parameter_node()

    def cleanup(self):
        """
        Called when the application closes and the module widget is destroyed.
        """
        self.removeObservers()
        slicer.util.mainWindow().removeDockWidget(self.timeline_widget)

    def load_timeline(self):
        try:
            qt.QApplication.setOverrideCursor(qt.Qt.WaitCursor)
            slice_node: vtkMRMLSliceNode = self.parameter_node.GetNodeReference(
                self.INPUT_SLICE
            )
            if slice_node is None:
                return

            slice_widget: slicer.qMRMLSliceWidget = (
                slicer.app.layoutManager().sliceWidget(slice_node.GetLayoutName())
            )
            if slice_widget is None:
                return

            sequence_browser_node: vtkMRMLSequenceBrowserNode = (
                self.parameter_node.GetNodeReference(self.INPUT_SEQUENCE_BROWSER)
            )

            self.timeline_widget.initialize(slice_widget, sequence_browser_node)
        finally:
            qt.QApplication.restoreOverrideCursor()

    def btn_toggle_timeline_clicked(self):
        if self.timeline_widget is not None:
            self.timeline_widget.setVisible(not self.timeline_widget.isVisible())

    def enter(self):
        """
        Called each time the user opens this module.
        """
        # Make sure the parameter node exists and is observed.
        self.initialize_parameter_node()

    def exit(self):
        """
        Called each time the user opens a different module.
        """
        # Do not react to parameter node changes (the GUI will be updated when the user
        # enters into the module)
        self.removeObserver(
            self.parameter_node,
            vtkCommand.ModifiedEvent,
            self.update_gui_from_parameter_node,
        )

    def on_scene_start_close(self, caller: vtkMRMLScene, event: str):
        """
        Called just before the scene is closed.
        """
        # The parameter node will be reset, do not use it anymore.
        self.set_parameter_node(None)
        slicer.util.mainWindow().removeDockWidget(self.timeline_widget)

    def on_scene_end_close(self, caller: vtkMRMLScene, event: str):
        """
        Called just after the scene is closed.
        """
        # If this module is shown while the scene is closed then recreate a new
        # parameter node immediately.
        if self.parent.isEntered:
            self.initialize_parameter_node()

    def initialize_parameter_node(self):
        """
        Ensure that the parameter node exists and is observed.
        """
        # The parameter node stores all user choices in parameter values, node
        # selections, etc. so that when the scene is saved and reloaded, these settings
        # are restored.
        if self.logic is not None:
            self.set_parameter_node(self.logic.getParameterNode())

    def set_parameter_node(self, node: Optional[vtkMRMLScriptedModuleNode]):
        """
        Set and observe the parameter node. Observation is needed because when the
        parameter node is changed then the GUI must be updated immediately.
        """
        if node is not None:
            self.logic.set_default_parameters(node)

        # Unobserve the previously selected parameter node and add an observer to the
        # newly selected. Changes of the parameter node are observed so that whenever
        # the parameters are changed by a script or any other module those changes are
        # reflected immediately in the GUI.
        if self.parameter_node is not None:
            self.removeObserver(
                self.parameter_node,
                vtkCommand.ModifiedEvent,
                self.update_gui_from_parameter_node,
            )

        self.parameter_node = node

        if self.parameter_node is not None:
            self.addObserver(
                self.parameter_node,
                vtkCommand.ModifiedEvent,
                self.update_gui_from_parameter_node,
            )

        # Initial GUI update
        self.update_gui_from_parameter_node()

    def update_gui_from_parameter_node(self, caller=None, event=None):
        """
        This method is called whenever the parameter node is changed. The module GUI is
        updated to show the current state of the parameter node.
        """
        if self.parameter_node is None or self.updating_gui_from_parameter_node:
            return

        # Make sure that the GUI changes do not call updateParameterNodeFromGUI (it
        # could cause an infinite loop)
        self.updating_gui_from_parameter_node = True

        for ref_name, widget in self.mrml_node_widgets.items():
            widget.setCurrentNode(self.parameter_node.GetNodeReference(ref_name))

        # All the GUI updates are done
        self.updating_gui_from_parameter_node = False

    def update_parameter_node_from_gui(self, caller=None, event=None):
        """
        This method is called when the user makes any change in the GUI. The changes are
        saved into the parameter node (so that they are restored when the scene is saved
        and loaded).
        """
        if self.parameter_node is None or self.updating_gui_from_parameter_node:
            return

        # Modify all properties in a single batch
        was_modified = self.parameter_node.StartModify()

        for ref_name, widget in self.mrml_node_widgets.items():
            self.parameter_node.SetNodeReferenceID(ref_name, widget.currentNodeID)

        self.parameter_node.EndModify(was_modified)

    def on_dummy_button_clicked(self):
        """
        Run the processing when the user clicks the "Dummy" button.
        """
        try:
            self.logic.process()
        except Exception as e:
            slicer.util.errorDisplay("Failed to compute results: " + str(e))
            traceback.print_exc()


class TimelineWidget(qt.QDockWidget):
    # Current progress as a number from 0 to 100
    progressUpdate = qt.Signal(int)

    def __init__(self, parent: Optional[qt.QWidget] = None):

        # Qt widget initialization

        qt.QDockWidget.__init__(self, parent)

        container = qt.QWidget()
        container.setLayout(qt.QGridLayout())
        container.layout().setAlignment(qt.Qt.AlignTop | qt.Qt.AlignLeft)

        scroll_area = qt.QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setWidget(container)
        scroll_area.installEventFilter(self)

        self.setAllowedAreas(qt.Qt.TopDockWidgetArea | qt.Qt.BottomDockWidgetArea)
        self.setWidget(scroll_area)

        # Attributes

        self.slice_widget: Optional[slicer.qMRMLSliceWidget] = None
        self.sequence_browser_node: Optional[vtkMRMLSequenceBrowserNode] = None

        # For enabling panning inside the scroll area
        self.mouse_pos = None
        self.move_start = False

        # For storing the current state while rendering the slice images
        self.current_slice_offset = 0
        self.current_selected_item_number = 0
        self.current_field_of_view = [0.0] * 3

        # For enabling selection of a slice image
        self.row_selected = 0
        self.col_selected = 0

    def initialize(
        self,
        slice_widget: slicer.qMRMLSliceWidget,
        sequence_browser_node: Optional[vtkMRMLSequenceBrowserNode] = None,
    ):
        self.progress(0)

        # Remove observers from previously stored objects
        if self.slice_widget is not None:
            self.slice_widget.mrmlSliceNode().RemoveObserver(vtkCommand.ModifiedEvent)
        if self.sequence_browser_node is not None:
            self.sequence_browser_node.RemoveObserver(vtkCommand.ModifiedEvent)

        # Store objects
        self.slice_widget = slice_widget
        self.sequence_browser_node = sequence_browser_node

        # Add observers to newly stored objects
        self.slice_widget.mrmlSliceNode().AddObserver(
            vtkCommand.ModifiedEvent, self.slice_node_modified
        )
        if self.sequence_browser_node is not None:
            self.sequence_browser_node.AddObserver(
                vtkCommand.ModifiedEvent, self.sequence_browser_node_modified
            )

        self.reset()
        self.progress(100)

    # Properties

    @property
    def grid(self) -> qt.QGridLayout:
        return self.widget().widget().layout()

    @property
    def rows(self):
        return self.grid.rowCount()

    @property
    def cols(self):
        return self.grid.columnCount()

    @property
    def scroll_area(self) -> qt.QScrollArea:
        return self.widget()

    @property
    def vertical_scroll_bar(self) -> qt.QScrollBar:
        return self.scroll_area.verticalScrollBar()

    @property
    def horizontal_scroll_bar(self):
        return self.scroll_area.horizontalScrollBar()

    @property
    def slice_logic(self) -> vtkMRMLSliceLogic:
        slice_logic: vtkMRMLSliceLogic = self.slice_widget.sliceLogic()
        return slice_logic

    @property
    def slice_bounds(self) -> List[float]:
        b = [0.0] * 6
        self.slice_logic.GetSliceBounds(b)
        return b

    # Event handlers

    def eventFilter(self, source: qt.QObject, event: qt.QEvent) -> bool:
        if source == self.scroll_area:
            return self.filter_scroll_area_events(event)
        return False

    def filter_scroll_area_events(self, event: qt.QEvent):
        """
        Enable panning of the timeline when dragging while the right mouse button is
        pressed.
        """
        if event.type() == qt.QEvent.MouseMove:
            if not (event.buttons() & qt.Qt.RightButton):
                return False
            if not self.move_start:
                self.move_start = True
                self.mouse_pos = event.globalPos()
            else:
                p = event.globalPos()
                delta = p - self.mouse_pos
                self.horizontal_scroll_bar.setValue(
                    self.horizontal_scroll_bar.value - delta.x()
                )
                self.vertical_scroll_bar.setValue(
                    self.vertical_scroll_bar.value - delta.y()
                )
                self.mouse_pos = p
            return True
        elif event.type() == qt.QEvent.MouseButtonRelease:
            self.move_start = False
            return True
        else:
            return False

    def sequence_browser_node_modified(
        self,
        observer: vtkMRMLSequenceBrowserNode,
        event_id: str,
    ):
        selected_item_number = observer.GetSelectedItemNumber()
        self.select_timeline_entry(None, selected_item_number)

    def slice_node_modified(
        self,
        observer: vtkMRMLSliceNode,
        event_id: str,
    ):
        slice_offset = observer.GetSliceOffset()
        self.select_timeline_entry(slice_offset, None)

    # Other methods

    def progress(self, p: int):
        self.progressUpdate.emit(p)
        slicer.app.processEvents(qt.QEventLoop.ExcludeUserInputEvents)

    def reset(self):
        self.begin_render_slice_images()

        # Calculate the total number of rows and cols
        bounds = self.slice_bounds
        volume_slice_spacing = self.slice_logic.GetLowestVolumeSliceSpacing()
        rows = int((bounds[5] - bounds[4]) / volume_slice_spacing[2])
        cols = 1
        if self.sequence_browser_node is not None:
            cols = self.sequence_browser_node.GetNumberOfItems()

        # Create placeholder widgets for the images
        for row in range(rows):
            self.progress(math.ceil(100 * row / rows))
            for col in range(cols):
                w = TimelineEntryWidget(
                    self.slice_widget,
                    self.slice_logic,
                    self.sequence_browser_node,
                    row,
                    col,
                )
                w.selected.connect(self.update_slice_widget)
                w.load()
                self.grid.addWidget(w, row, col)

        self.end_render_slice_images()

    def save_state(self):
        if self.sequence_browser_node is not None:
            self.current_selected_item_number = (
                self.sequence_browser_node.GetSelectedItemNumber()
            )
        self.current_slice_offset = self.slice_logic.GetSliceOffset()
        self.current_field_of_view = self.slice_widget.mrmlSliceNode().GetFieldOfView()

    def restore_state(self):
        if self.sequence_browser_node is not None:
            self.sequence_browser_node.SetSelectedItemNumber(
                self.current_selected_item_number
            )
        self.slice_logic.SetSliceOffset(self.current_slice_offset)
        self.slice_widget.mrmlSliceNode().SetFieldOfView(*self.current_field_of_view)

    def begin_render_slice_images(self):
        slicer.app.pauseRender()
        clear_layout(self.grid)
        self.save_state()

    def end_render_slice_images(self):
        self.restore_state()
        self.select_timeline_entry()
        self.slice_widget.sliceView().forceRender()
        slicer.app.resumeRender()

    def select_timeline_entry(
        self,
        slice_offset: Optional[float] = None,
        selected_item_number: Optional[int] = None,
    ):
        if slice_offset is None:
            slice_offset = self.slice_logic.GetSliceOffset()
        if selected_item_number is None:
            selected_item_number = 0
            if self.sequence_browser_node is not None:
                selected_item_number = (
                    self.sequence_browser_node.GetSelectedItemNumber()
                )

        self.unselect_current_timeline_entry()
        self.row_selected = TimelineWidget.row_for_slice_offset(
            self.slice_logic, slice_offset
        )
        self.col_selected = selected_item_number
        self.select_current_timeline_entry()

    def update_slice_widget(self, row: int, col: int):
        if row == self.row_selected and col == self.col_selected:
            return
        self.unselect_current_timeline_entry()
        self.row_selected = row
        self.col_selected = col
        self.sync_slice_widget()

    def unselect_current_timeline_entry(self):
        item = self.grid.itemAtPosition(self.row_selected, self.col_selected)
        if item is not None:
            w: TimelineEntryWidget = item.widget()
            w.is_selected = False

    def select_current_timeline_entry(self):
        item = self.grid.itemAtPosition(self.row_selected, self.col_selected)
        if item is not None:
            w: TimelineEntryWidget = item.widget()
            w.is_selected = True

    def sync_slice_widget(self):
        slice_offset = TimelineWidget.slice_offset_for_row(
            self.slice_logic, self.row_selected
        )
        selected_item_number = self.col_selected

        self.slice_logic.SetSliceOffset(slice_offset)
        if self.sequence_browser_node is not None:
            self.sequence_browser_node.SetSelectedItemNumber(selected_item_number)
        self.slice_widget.sliceView().forceRender()

    @staticmethod
    def slice_offset_for_row(slice_logic: vtkMRMLSliceLogic, row: int):
        bounds = [0.0] * 6
        slice_logic.GetSliceBounds(bounds)
        min_slice_y = bounds[4]
        slice_thickness = slice_logic.GetLowestVolumeSliceSpacing()[2]
        return min_slice_y + slice_thickness * row

    @staticmethod
    def row_for_slice_offset(slice_logic: vtkMRMLSliceLogic, slice_offset: float):
        bounds = [0.0] * 6
        slice_logic.GetSliceBounds(bounds)
        min_slice_y = bounds[4]
        slice_thickness = slice_logic.GetLowestVolumeSliceSpacing()[2]
        return int((slice_offset - min_slice_y) / slice_thickness)


class TimelineEntryWidget(qt.QLabel):
    DEFAULT_IMAGE_SIZE = 256

    selected = qt.Signal(int, int)

    def __init__(
        self,
        slice_widget: slicer.qMRMLSliceWidget,
        slice_logic: vtkMRMLSliceLogic,
        sequence_browser_node: vtkMRMLSequenceBrowserNode,
        row: int,
        col: int,
        parent: Optional[qt.QWidget] = None,
    ):
        super().__init__(parent)

        self.slice_widget = slice_widget
        self.slice_logic = slice_logic
        self.sequence_browser_node = sequence_browser_node
        self.row = row
        self.col = col

        self._image = None
        self._is_selected = False

        self._set_border_color("black")

    @property
    def is_selected(self):
        return self._is_selected

    @is_selected.setter
    def is_selected(self, value):
        self._is_selected = value
        self._update_border_color()

    def mousePressEvent(self, event: qt.QMouseEvent):
        if event.buttons() & qt.Qt.LeftButton:
            self.is_selected = True
            self.selected.emit(self.row, self.col)

    def enterEvent(self, event: qt.QEvent):
        self._set_border_color("red")

    def leaveEvent(self, event: qt.QMouseEvent):
        if self.is_selected:
            self._set_border_color("green")
        else:
            self._set_border_color("black")

    def load(self):
        if self._image is not None:
            return

        slice_offset = TimelineWidget.slice_offset_for_row(self.slice_logic, self.row)
        selected_item_number = self.col
        self.slice_logic.SetSliceOffset(slice_offset)
        if (
            self.sequence_browser_node is not None
            and self.sequence_browser_node.GetNumberOfItems() > 1
        ):
            self.sequence_browser_node.SetSelectedItemNumber(selected_item_number)

        self.slice_widget.sliceView().forceRender()

        self._image = qt.QWidget.grab(self.slice_widget.sliceView()).toImage()
        self._image = self._image.scaled(
            self.DEFAULT_IMAGE_SIZE,
            self.DEFAULT_IMAGE_SIZE,
            qt.Qt.KeepAspectRatio,
        )

        self.setPixmap(qt.QPixmap.fromImage(self._image))

    def _update_border_color(self):
        if self.is_selected:
            self._set_border_color("green")
        else:
            self._set_border_color("black")

    def _set_border_color(self, color: str):
        self.setStyleSheet("border: 1px solid %s;" % color)


class DeepArcTimelineLogic(ScriptedLoadableModuleLogic):
    """
    This class should implement all the actual computation done by your module. The
    interface should be such that other python code can import this class and make use
    of the functionality without requiring an instance of the Widget.
    """

    def __init__(self):
        super().__init__()

    def set_default_parameters(self, node: vtkMRMLScriptedModuleNode):
        """
        Initialize the parameter node with default settings.
        """
        pass

    def process(self):
        """
        Run the processing algorithm. Can be used without GUI widget.
        """
        pass


class DeepArcTimelineTest(ScriptedLoadableModuleTest):
    """
    This is the test case for the scripted module.
    """

    def runTest(self):
        """
        Run as few or as many tests as needed here.
        """
        self.setUp()
        self.test_dummy()

    def setUp(self):
        """
        Do whatever is needed to reset the state - typically a scene clear will be
        enough.
        """
        slicer.mrmlScene.Clear()

    def test_dummy(self):
        """
        Ideally you should have several levels of tests. At the lowest level the tests
        should exercise the functionality of the logic with different inputs (both valid
        and invalid). At higher levels your tests should emulate the way the user would
        interact with your code and confirm that it still works the way you intended.
        One of the most important features of the tests is that it should alert other
        developers when their changes will have an impact on the behavior of your
        module. For example, if a developer removes a feature that you depend on, your
        test should break so they know that the feature is needed.
        """
        self.delayDisplay("Dummy test passed.")


def clear_layout(layout: qt.QLayout):
    for i in reversed(range(layout.count())):
        layout.itemAt(i).widget().setParent(None)
