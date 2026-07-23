<img src="img/handwriter.png" align="right" width="100px">

# Handwriter

**README:**  <a href="https://github.com/ImMALWARE/handwriter/blob/main/README_en.md"><img src="img/en_flag.png" height="21" align="center"/>In English</a> <a href="https://github.com/ImMALWARE/handwriter/blob/main/README.md"><img src="img/ru_flag.png" height="26" align="center"/>На русском</a>

---

*Handwriter* is a tool that converts typed text into handwriting and lets you create custom fonts from your own handwriting. The software generates ready-to-use vector files (SVG) and G-code to automate drawing on plotters.

## Font Editor (Creating a font)

To create a font from your handwriting, on the **Font** tab, click the **Font Editor** button. In the window that opens, the following tools will be available to you:
![](https://raw.githubusercontent.com/ImMALWARE/handwriter/refs/heads/main/img/screenshot_font_en.png)
### Working with characters (Left panel)
* **Search**: A field to quickly search for a specific character in your font.
* **Character list**: Displays all characters added to the font and the number of their variants. You can right-click any character to **Delete** it.
* **Adding a character**: At the bottom of the left panel, enter a single character (letter, number, or punctuation mark) in the text field and click the **"+"** button to add it to your font.

### Canvas and drawing (Center panel)
* Select a character in the left panel to start drawing. Draw a small letter in the highlighted cell. Letters can extend beyond the highlighted cell; for example, UPPERCASE LETTERS have their top part one cell higher; the letters y, p, g have their bottom part one cell lower. All letters should be approximately the same size.
* **Drawing characters**: Hold down the **left mouse button** (or use a graphics tablet) and drag the cursor across the canvas to draw the character.
* **Connection points**: In order for the letters to connect seamlessly with each other when generating text, they need connection points. When you **right-click** on a specific point on the character, a menu will appear to set the **start** and **end** of the character. The start is where the connection line from the previous character will lead. The end is where the connection line to the next character will begin. The start and end points can be dragged with the mouse. Setting connection points is not required; punctuation marks and numbers do not need them.

### Character variants and canvas control (Bottom panel under the canvas)
* To make the text look natural, you can draw several different variants for each letter. A random variant of the character will be chosen each time during generation.
* **Left/right arrows (`<` and `>`)**: Switch between the drawn variants of the current character.
* **"+" button (Add variant)**: Add a new empty variant for the current character.
* **Trash button (Delete variant)**: Delete the current variant.
* **Eraser button (Clear)**: Erase all drawn lines on the current variant.
* **Magnifying glass buttons (+ / -)**: **Zoom in** or **Zoom out** of the canvas.
* **"Fit" button**: Adjust the scale so that the character fits in the window.

### Font editor ribbon (Top panel)
* **File**:
  * **New font**: Create an empty font.
  * **Open**: Open an existing font (`.hfont`).
  * **Save**: Save the current font.
  * **Save as**: Save the current font under a new name.
* **History**:
  * **Undo**: Undo the last action (drawing or deleting).
  * **Redo**: Redo the undone action.
* **Connection points**: Shows the coordinates of the added start and end points.

## Main application window
![](https://raw.githubusercontent.com/ImMALWARE/handwriter/refs/heads/main/img/screenshot_main_en.png)
The main window is divided into a text editor (left) and a result preview (right). At the top is a control ribbon with several tabs.

### "Home" tab
* **File**:
  * **New**: Create an empty document project.
  * **Open**: Load a previously saved document (`.hwdoc`).
  * **Save**: Save the current document.
  * **Save as**: Save the document under a different name.
* **History**: 
  * **Undo / Redo**: Undoes or redoes actions in the text editor.
* **Clipboard**: 
  * **Cut**, **Copy**, **Paste**: Text editing functions.
* **Font**:
  * **Open font**: Select a `.hfont` font file for the current document.

### "Font" tab
* **Font**:
  * **Open font**: Select a `.hfont` font file for the current document.
  * **Font Editor**: Open the font editor window.
  * **Close**: Remove the current font from the document.
* **Size**:
  * **Font Size**: Adjust the scale of letters. 1.0 is the same scale as in the font editor, 2.0 is twice as large, 0.5 is half as large.
  * **Spacing**: The distance between lines of text in millimeters (mm).
* **Alignment**:
  * **Align left**, **Align center**, **Align right**: Formats the selected text. When clicked, the text is wrapped in BB-codes (e.g., `[center]...[/center]`).

### "Paper" tab
* **Preset**:
  * **Load preset**: Load ready-made dimensions and margin settings (`.hwpap`).
  * **Save preset**: Save the current dimensions and margin settings to a `.hwpap` file.
* **Paper size**:
  * **Width** and **Height**: Adjust the physical size of the sheet in millimeters.
* **Margins**:
  * **Top**: Indent from the top edge.
  * **First Top**: Indent from the top edge that applies only to the first page of the document; overrides the **Top** margin value.
  * **Bottom**: Indent from the bottom edge.
  * **Left** and **Right**: Indents on the sides.
  * **In cells**: Switches the margin measurement mode from millimeters (mm) to cells (cl). The size of one cell is 5 mm.
* **Preview**:
  * **Toggle grid**: Enable or disable the display of a cell grid on the canvas on the right.

### "Export" tab
* **Export to SVG**: Opens a window to select a folder where each page of the document will be saved as a separate `.svg` file.
* **Export to G-code**: Opens a window to select a folder where G-code files will be saved for use on plotters. In the "G-code Parameters" section, you can set the following parameters:
  * **Feed**: Movement speed with the pen down (mm/min).
  * **Passing Feed**: Movement speed with the pen up (mm/min).
  * **Penetration Feed**: Pen up/down speed (mm/min).
  * **Z-Up (Travel)**: Pen lift height when moving without writing (mm).
  * **Z-Down (Draw)**: Pen lowering height at which it touches the paper (mm).

### Other controls

* **Text editor (Left)**: You can type, paste, and edit text in this field. Line numbers are shown, and the current line is highlighted. You can use hotkeys: `Ctrl+Z` (Undo), `Ctrl+Y` (Redo), `Ctrl+S` (Save).
* **Preview canvas (Right)**:
  * You can move around the canvas by holding the left mouse button.
  * Zooming is done by holding **Ctrl + Mouse wheel**, or via the buttons in the bottom right corner of the canvas: **Zoom out (-)**, **Zoom in (+)**, and **Fit**.
* **Status bar (At the very bottom of the window)**: Notifications are displayed here. For example, if the loaded font is missing characters typed in the editor. Or if there are errors in BBCode tags.
