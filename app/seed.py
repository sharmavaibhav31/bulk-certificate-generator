from sqlalchemy.orm import Session
from app.models import Template

BUILTIN_TEMPLATES = [
    {
        "key": "classic",
        "name": "Classic Gold",
        "kind": "builtin",
        "layout": {"name_y": 45.0, "course_y": 60.0, "date_y": 75.0},
    },
    {
        "key": "modern",
        "name": "Modern Minimal",
        "kind": "builtin",
        "layout": {"name_y": 42.0, "course_y": 58.0, "date_y": 75.0},
    },
    {
        "key": "minimal",
        "name": "Minimal Clean",
        "kind": "builtin",
        "layout": {"name_y": 45.0, "course_y": 60.0, "date_y": 78.0},
    },
    {
        "key": "elegant",
        "name": "Elegant Navy",
        "kind": "builtin",
        "layout": {"name_y": 38.0, "course_y": 54.0, "date_y": 70.0},
    },
    {
        "key": "bold",
        "name": "Bold Tech",
        "kind": "builtin",
        "layout": {"name_y": 44.0, "course_y": 62.0, "date_y": 80.0},
    },
]


def seed_builtin_templates(db: Session) -> None:
    """
    Seed 5 builtin certificate templates if they do not already exist in the database.
    """
    for tpl_data in BUILTIN_TEMPLATES:
        existing = (
            db.query(Template)
            .filter(Template.key == tpl_data["key"])
            .first()
        )
        if not existing:
            template = Template(
                name=tpl_data["name"],
                kind=tpl_data["kind"],
                key=tpl_data["key"],
                layout=tpl_data["layout"],
                background_path=None,
                is_deleted=False,
            )
            db.add(template)
    db.commit()
