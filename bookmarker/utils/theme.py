"""Centralized theme management for Bookmarker."""

from PyQt6.QtWidgets import QApplication


class ThemeManager:
    """Single source of truth for all application theming."""

    _dark_mode: bool = False

    # Dark palette
    _D_BG = "#1e1e1e"
    _D_BG_ALT = "#252526"
    _D_BG_RAISED = "#2d2d2d"
    _D_BG_INPUT = "#3c3c3c"
    _D_BG_HOVER = "#4c4c4c"
    _D_BORDER = "#3d3d3d"
    _D_FG = "#d4d4d4"
    _D_FG_DIM = "#888888"
    _D_SELECTION = "#264f78"
    _D_ACCENT = "#0078d4"

    # Light palette
    _L_BG = "#ffffff"
    _L_BG_ALT = "#f9f9f9"
    _L_BG_RAISED = "#f3f3f3"
    _L_BG_HOVER = "#e5e5e5"
    _L_BORDER = "#d4d4d4"
    _L_FG = "#1e1e1e"
    _L_FG_DIM = "#666666"
    _L_SELECTION = "#cce8ff"
    _L_ACCENT = "#0078d4"

    DARK_STYLESHEET = f"""
        QMainWindow {{
            background-color: {_D_BG};
            color: {_D_FG};
        }}
        QWidget {{
            background-color: {_D_BG};
            color: {_D_FG};
        }}
        QMenu {{
            background-color: {_D_BG_RAISED};
            color: {_D_FG};
            border: 1px solid {_D_BORDER};
        }}
        QMenu::item:selected {{
            background-color: {_D_ACCENT};
        }}
        QPushButton {{
            background-color: {_D_BG_INPUT};
            color: {_D_FG};
            border: 1px solid {_D_BORDER};
            padding: 6px 16px;
            border-radius: 3px;
            font-size: 13px;
        }}
        QPushButton:hover {{
            background-color: {_D_BG_HOVER};
        }}
        QPushButton:disabled {{
            background-color: {_D_BG_RAISED};
            color: {_D_FG_DIM};
        }}
        QLabel {{
            color: {_D_FG};
            background: transparent;
        }}
        QLineEdit {{
            background-color: {_D_BG_INPUT};
            color: {_D_FG};
            border: 1px solid {_D_BORDER};
            padding: 4px 8px;
            border-radius: 3px;
        }}
        QComboBox {{
            background-color: {_D_BG_INPUT};
            color: {_D_FG};
            border: 1px solid {_D_BORDER};
            padding: 4px 8px;
            border-radius: 3px;
        }}
        QComboBox QAbstractItemView {{
            background-color: {_D_BG_RAISED};
            color: {_D_FG};
            selection-background-color: {_D_ACCENT};
        }}
        QTreeWidget {{
            background-color: {_D_BG_INPUT};
            color: {_D_FG};
            border: 1px solid {_D_BORDER};
            selection-background-color: {_D_SELECTION};
        }}
        QTreeWidget::item:selected {{
            background-color: {_D_SELECTION};
        }}
        QTextEdit {{
            background-color: {_D_BG};
            color: {_D_FG};
            border: 1px solid {_D_BORDER};
        }}
        QDialog {{
            background-color: {_D_BG};
            color: {_D_FG};
        }}
        QCheckBox {{
            color: {_D_FG};
            background: transparent;
        }}
        QToolBar {{
            background-color: {_D_BG_ALT};
            border: none;
            spacing: 4px;
        }}
        QProgressBar {{
            background-color: {_D_BG_INPUT};
            border: 1px solid {_D_BORDER};
            border-radius: 3px;
            text-align: center;
            color: {_D_FG};
        }}
        QProgressBar::chunk {{
            background-color: {_D_ACCENT};
            border-radius: 2px;
        }}
        QScrollBar:vertical {{
            background-color: {_D_BG_RAISED};
            width: 10px;
        }}
        QScrollBar::handle:vertical {{
            background-color: #5a5a5a;
            border-radius: 4px;
            min-height: 20px;
        }}
        QScrollBar::add-line, QScrollBar::sub-line {{
            height: 0px;
        }}
        QScrollBar::add-page, QScrollBar::sub-page {{
            background: none;
        }}
    """

    LIGHT_STYLESHEET = f"""
        QMainWindow {{
            background-color: {_L_BG};
            color: {_L_FG};
        }}
        QWidget {{
            background-color: {_L_BG};
            color: {_L_FG};
        }}
        QMenu {{
            background-color: {_L_BG};
            color: {_L_FG};
            border: 1px solid {_L_BORDER};
        }}
        QMenu::item:selected {{
            background-color: {_L_ACCENT};
            color: white;
        }}
        QPushButton {{
            background-color: {_L_BG_RAISED};
            color: {_L_FG};
            border: 1px solid {_L_BORDER};
            padding: 6px 16px;
            border-radius: 3px;
            font-size: 13px;
        }}
        QPushButton:hover {{
            background-color: {_L_BG_HOVER};
        }}
        QPushButton:disabled {{
            background-color: {_L_BG_RAISED};
            color: {_L_FG_DIM};
        }}
        QLabel {{
            color: {_L_FG};
            background: transparent;
        }}
        QLineEdit {{
            background-color: {_L_BG};
            color: {_L_FG};
            border: 1px solid {_L_BORDER};
            padding: 4px 8px;
            border-radius: 3px;
        }}
        QComboBox {{
            background-color: {_L_BG};
            color: {_L_FG};
            border: 1px solid {_L_BORDER};
            padding: 4px 8px;
            border-radius: 3px;
        }}
        QComboBox QAbstractItemView {{
            background-color: {_L_BG};
            color: {_L_FG};
            selection-background-color: {_L_ACCENT};
            selection-color: white;
        }}
        QTreeWidget {{
            background-color: {_L_BG};
            color: {_L_FG};
            border: 1px solid {_L_BORDER};
            selection-background-color: {_L_SELECTION};
        }}
        QTreeWidget::item:selected {{
            background-color: {_L_SELECTION};
        }}
        QTextEdit {{
            background-color: {_L_BG};
            color: {_L_FG};
            border: 1px solid {_L_BORDER};
        }}
        QDialog {{
            background-color: {_L_BG};
            color: {_L_FG};
        }}
        QCheckBox {{
            color: {_L_FG};
            background: transparent;
        }}
        QToolBar {{
            background-color: {_L_BG_ALT};
            border: none;
            spacing: 4px;
        }}
        QProgressBar {{
            background-color: {_L_BG_RAISED};
            border: 1px solid {_L_BORDER};
            border-radius: 3px;
            text-align: center;
            color: {_L_FG};
        }}
        QProgressBar::chunk {{
            background-color: {_L_ACCENT};
            border-radius: 2px;
        }}
        QScrollBar:vertical {{
            background-color: {_L_BG_RAISED};
            width: 10px;
        }}
        QScrollBar::handle:vertical {{
            background-color: #c1c1c1;
            border-radius: 4px;
            min-height: 20px;
        }}
        QScrollBar::add-line, QScrollBar::sub-line {{
            height: 0px;
        }}
        QScrollBar::add-page, QScrollBar::sub-page {{
            background: none;
        }}
    """

    @classmethod
    def apply(cls, dark: bool) -> None:
        """Apply the theme globally and store the current mode."""
        cls._dark_mode = dark
        app = QApplication.instance()
        if app:
            app.setStyleSheet(cls.DARK_STYLESHEET if dark else cls.LIGHT_STYLESHEET)

    @classmethod
    def is_dark_mode(cls) -> bool:
        return cls._dark_mode
