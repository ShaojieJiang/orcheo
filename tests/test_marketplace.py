from orcheo.marketplace.catalog import MarketplaceCatalog, MarketplaceEntry


def test_marketplace_catalog_registers_and_lists_entries() -> None:
    catalog = MarketplaceCatalog()
    catalog.register(
        MarketplaceEntry(
            slug="slack-notify",
            name="Slack Notification",
            description="Send alerts to Slack",
            tags=("communication", "slack"),
        )
    )
    entries = list(catalog.list())
    assert entries[0].slug == "slack-notify"
