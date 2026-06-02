# Computer Vision Bot (Proof of Concept)

This repository contains a single Python script (`main.py`) that demonstrates the application of computer vision (OpenCV) and GUI automation (`pyautogui`) in a simulated, isometric grid environment. 

## ⚠️ Legal & Educational Disclaimer

**This project is strictly for educational and research purposes.**
* **No Distribution of Assets:** This repository only contains the logical Python script. It does **not** contain any proprietary game assets, images, or template files required to run the script.
* **As-Is:** This code is provided as a programming experiment to demonstrate multi-scale template matching and isometric coordinate mathematics. It is not a commercial product.

---

## Technical Overview

The script (`main.py`) demonstrates several advanced automation concepts:
* **Multi-Scale Template Matching:** Uses `cv2.matchTemplate` to dynamically resize and find UI elements regardless of camera zoom.
* **Isometric Trajectory Math:** Calculates 2:1 ratio diagonals to perform "lawnmower" sweeps across an isometric grid.
* **State Management:** Uses dynamic coordinate sorting to find extreme "bottom-most" or "right-most" UI anchors.
* **Failsafe Engineering:** Implements UI deadzones, OS-level window focusing (`pygetwindow`), and thread-injection termination (`ctypes`) to prevent runaway automation.

---

## Prerequisites & Setup

Because this is a raw script, it will not run out of the box. You must build your own image recognition environment.

1. **Dependencies:**
   Make sure you have Python installed, then run the following command in your terminal:
   `pip install opencv-python numpy mss pyautogui pygetwindow`

2. **The `templates` Folder:**
   The script expects a folder named `templates` in the exact same directory as `main.py`. You must manually take screenshots of your own game environment, crop them tightly, and name them according to the references in the code (e.g., `soil.jpg`, `sickle.jpg`, `ready_wheat.jpg`). 

3. **Environment Calibration:**
   The bot's coordinate mathematics and taskbar deadzones are calibrated for a **1920x1080** display running the MEmu Android Emulator (`MEmuHeadless.exe` / `MEmu.exe`).

---

## License

This project is licensed under the MIT License. See the `LICENSE` file for details. Use at your own risk.