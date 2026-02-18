# Site Flow Config

Site-specific handlers for modals, popups, and UI quirks. Add new cases here instead of hardcoding in tests or executor.

## Triggers

| Trigger | When it runs |
|---------|--------------|
| `after_pincode_check` | After clicking "check" beside pincode (LG shows "Select delivery option" popup) |
| `before_select_delivery` | Before selecting free delivery option |
| `before_checkout` | Before clicking checkout |

## Adding New Handlers

Edit `lg_flow_config.json` or create `{site}_flow_config.json` (e.g., `amazon_flow_config.json`):

```json
{
  "trigger": "before_select_delivery",
  "actions": [
    {
      "type": "dismiss_modal",
      "button_texts": ["OK", "Continue", "Select delivery"]
    },
    {
      "type": "wait",
      "ms": 1000
    }
  ]
}
```

## Action Types

- **dismiss_modal**: Click button with given text (tries button, link, text)
- **run_interrupt_handler**: Run generic interrupt handler (dismiss common modals)
- **wait**: Pause for `ms` milliseconds

## Adding New Sites

1. Create `{sitename}_flow_config.json` in this folder
2. Update `flow_config_loader.py` `_match_site()` to map URL to site key
