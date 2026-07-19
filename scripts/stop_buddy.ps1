# Ask MadoMochi to close (posts WM_CLOSE to its window).
python -c "import ctypes; h = ctypes.windll.user32.FindWindowW(None, 'MadoMochi'); ctypes.windll.user32.PostMessageW(h, 0x0010, 0, 0) if h else print('MadoMochi is not running')"
