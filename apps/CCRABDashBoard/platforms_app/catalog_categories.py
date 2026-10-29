"""Ordered catalog categories; the first matching category owns each station."""


PLATFORM_CATALOG_CATEGORIES = (
    {
        "key": "active",
        "label": "Active",
        "matches": lambda properties: properties.get("active") == 1,
    },
    # Keep this catch-all last so every station appears exactly once.
    {
        "key": "non-active",
        "label": "Non Active stations",
        "matches": lambda properties: True,
    },
)


def group_catalog_platforms(features, categories=PLATFORM_CATALOG_CATEGORIES):
    """Add categories before the catch-all to extend the catalog grouping."""
    groups = []
    for category in categories:
        groups.append({
            "key": category["key"],
            "label": category["label"],
            "features": [],
        })

    for feature in features:
        for category, group in zip(categories, groups):
            if category["matches"](feature.get("properties", {})):
                group["features"].append(feature)
                break
    return groups
