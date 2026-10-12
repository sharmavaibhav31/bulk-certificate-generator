from sqlalchemy.orm import Session
from app.models import Template

BUILTIN_TEMPLATES = [
    {
        "key": "classic",
        "name": "Classic Gold",
        "kind": "builtin",
        "required_fields": ["name", "title", "issued_date"],
        "layout": {
            "name_y": 45.0,
            "course_y": 62.0,
            "date_y": 78.0,
            "font": "dejavu_serif",
            "color": "#1A2530",
        },
    },
    {
        "key": "modern",
        "name": "Modern Minimal",
        "kind": "builtin",
        "required_fields": ["name", "title", "issued_date"],
        "layout": {
            "name_y": 42.0,
            "course_y": 60.0,
            "date_y": 76.0,
            "font": "dejavu_sans",
            "color": "#0F172A",
        },
    },
    {
        "key": "minimal",
        "name": "Minimal Clean",
        "kind": "builtin",
        "required_fields": ["name", "title", "issued_date"],
        "layout": {
            "name_y": 45.0,
            "course_y": 60.0,
            "date_y": 78.0,
            "font": "liberation_sans",
            "color": "#111827",
        },
    },
    {
        "key": "elegant",
        "name": "Elegant Navy",
        "kind": "builtin",
        "required_fields": ["name", "title", "issued_date"],
        "layout": {
            "name_y": 38.0,
            "course_y": 55.0,
            "date_y": 72.0,
            "font": "dejavu_serif",
            "color": "#0A192F",
        },
    },
    {
        "key": "bold",
        "name": "Bold Tech",
        "kind": "builtin",
        "required_fields": ["name", "title", "issued_date"],
        "layout": {
            "name_y": 44.0,
            "course_y": 62.0,
            "date_y": 80.0,
            "font": "dejavu_sans",
            "color": "#F8FAFC",
        },
    },
]


def seed_builtin_templates(db: Session) -> None:
    """
    Seed 5 builtin certificate templates if they do not already exist in the database.
    Updates required_fields if existing rows lack them.
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
                required_fields=tpl_data["required_fields"],
                background_path=None,
                is_deleted=False,
            )
            db.add(template)
        else:
            # Ensure required_fields is up to date
            existing.required_fields = tpl_data["required_fields"]
    db.commit()
