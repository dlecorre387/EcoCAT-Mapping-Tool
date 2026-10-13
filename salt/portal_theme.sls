{% set TETHYS_PERSIST = salt['environ.get']('TETHYS_PERSIST') %}
{% set STATIC_ROOT = salt['environ.get']('STATIC_ROOT') %}

Move_Custom_Theme_Files_to_Static_Root:
  cmd.run:
    - name: mv /tmp/custom_theme {{ STATIC_ROOT }}
    - shell: /bin/bash

Apply_Custom_Theme:
  cmd.run:
    - name: >
        tethys site
        --site-title "EcoCAT"
        --brand-text "EcoCAT (Ecosystem Conservation Assessment Tools)"
        --brand-image "custom_theme/images/EcoCAT_RGB_W.png"
        --favicon "custom_theme/images/EcoCAT_RGB_W_favicon.png"
        --primary-color "#669900"
        --secondary-color "#CDDC00"
        --primary-text-color "#ffffff"
        --primary-text-hover-color "#ffffff"
        --secondary-text-color "#000000"
        --secondary-text-hover-color "#000000"
        --background-color "#ffffff"
        --copyright "Copyright © 2026 Daniel Le Corre, Rob Critchlow, Tarciso Leão, Royal Botanic Gardens, Kew"
    - shell: /bin/bash