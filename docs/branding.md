# DESLOC icons in Home Assistant and HACS

DESLOC includes `brand/icon.png` and `brand/icon@2x.png` inside
`custom_components/desloc`. Home Assistant can use these local assets for the
integration. The **DESLOC Update** entity is created by HACS, however, and HACS
2.0.5 requests its picture from the external Home Assistant brands service. That
service can return an **icon not available** placeholder even when the installed
DESLOC package contains the correct images.

The related [HACS issue #5171](https://github.com/hacs/integration/issues/5171)
also covers missing images in the HACS catalog. On October 16, 2026, a maintainer
reported that this is fixed in Marketplace, planned for Home Assistant 2026.11.
That does not change the behavior of an existing HACS 2.0.5 installation.

## Show the icon on the update entity

This optional workaround uses Home Assistant's supported entity customization.
It changes the picture in the update dialog and other views that display the
update entity's picture. It does **not** change the HACS catalog listing.
Installing or updating DESLOC does not apply this customization automatically.

1. Find the actual DESLOC **update entity ID** under **Settings → Devices &
   services → Entities**, or **Developer tools → States**. The example below
   uses `update.desloc_experimental_update`, which an older installation may
   retain. Your ID may differ; use your own ID without renaming it.
2. Copy the installed `custom_components/desloc/brand/icon.png` into
   `www/desloc/icon.png` in the Home Assistant configuration directory. For an
   installation whose configuration is mounted at `/config`, the paths are:

   ```text
   /config/custom_components/desloc/brand/icon.png
   /config/www/desloc/icon.png
   ```

   Create `www/desloc` if needed. If you have not installed the integration yet,
   obtain the same icon from `custom_components/desloc/brand/icon.png` in the
   [stable release archive](https://github.com/ha-homelab/ha-desloc/releases/latest).
   If `www` itself is new, Home Assistant requires a restart before it serves
   files from that directory. See [hosting local files](https://www.home-assistant.io/integrations/http/#hosting-files).
3. Merge the following into `configuration.yaml`. Preserve existing
   `homeassistant:` and `customize:` entries: add the entity beneath the existing
   mapping instead of creating duplicate keys. If `customize:` already uses
   `!include customize.yaml`, put only the entity and its attributes into that
   included file, without the `homeassistant:` or `customize:` wrapper.

   ```yaml
   homeassistant:
     customize:
       update.desloc_experimental_update:
         entity_picture: /local/desloc/icon.png
   ```

   The same configuration is available in
   [examples/hacs-branding.yaml](../examples/hacs-branding.yaml). For an existing
   packages setup, see the alternative below. Configure this in one place only.
4. Check the configuration under **Developer tools → YAML → Check
   configuration**. After it passes, select **Reload → Location &
   customizations**, or run the `homeassistant.reload_core_config` action under
   **Developer tools → Actions**. Reloading this configuration sends no lock
   commands.
5. Open `/local/desloc/icon.png` on your Home Assistant URL and confirm that the
   image loads. Then reopen the DESLOC update dialog. If the old picture remains,
   run `homeassistant.update_entity` for your DESLOC **update entity**, and reload
   the browser page. This refreshes update metadata; it does not install an
   update or operate the lock.

Only the public project icon belongs in `www/desloc`. Files under `/local/` are
served without Home Assistant authentication; do not place credentials,
diagnostics, or configuration backups there.

### Alternative for an existing packages setup

If `configuration.yaml` already contains
`homeassistant: packages: !include_dir_named packages` with the appropriate YAML
indentation, copy [examples/hacs-branding.yaml](../examples/hacs-branding.yaml)
to `packages/desloc_branding.yaml`, and change the entity ID if needed. Keep its
`homeassistant:` wrapper. For clarity, the existing include would look like:

```yaml
homeassistant:
  packages: !include_dir_named packages
```

Do not add a second `homeassistant:` or `packages:` key, and do not also add the
same customization to `configuration.yaml`. For `!include_dir_merge_named`,
the file needs an outer package-name key; follow Home Assistant's
[package configuration documentation](https://www.home-assistant.io/docs/configuration/packages/)
instead of copying the example unchanged. Copy the image and perform the same
configuration check and reload described above.

## Removing the workaround

When your installed HACS or Marketplace version supplies the right image,
remove this entity's `entity_picture` customization, reload the core
configuration, and refresh the update entity. Remove the copied
`www/desloc/icon.png` only when no other dashboard or customization uses it.
Keep the integration's bundled `brand` directory intact.

For other entity attributes, see Home Assistant's
[entity customization documentation](https://www.home-assistant.io/docs/configuration/customizing-devices/).
