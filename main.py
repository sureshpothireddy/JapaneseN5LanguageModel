"""
main.py — LinguaBridge entry point.

Run with:  python main.py
"""

import sys


def main():
    if sys.version_info < (3, 11):
        print("LinguaBridge needs Python 3.11 or newer.")
        sys.exit(1)
    try:
        import customtkinter  # noqa: F401
    except ImportError:
        print("Missing dependencies. In your project folder run:\n"
              "    pip install -r requirements.txt")
        sys.exit(1)

    from database.db_manager import DBManager
    from lessons.loader import LessonValidationError
    from ui.main_window import MainWindow

    db = DBManager()
    try:
        app = MainWindow(db)
    except LessonValidationError as e:
        print(f"Lesson content error: {e}")
        sys.exit(1)
    app.mainloop()


if __name__ == "__main__":
    main()
