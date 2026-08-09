# ARDA Boot Visual Plan

## Objective

Carry the sovereign website's ceremonial language into the real boot chain so Arda feels like a constitutional substrate from firmware handoff onward.

## Visual Canon

Source basis:

- [arda-sovereign-website/index.html](/home/byron/Integritas-Mechanicus/arda-sovereign-website/index.html:1)
- [arda-sovereign-website/style.css](/home/byron/Integritas-Mechanicus/arda-sovereign-website/style.css:1)
- [arda-sovereign-website/README.md](/home/byron/Integritas-Mechanicus/arda-sovereign-website/README.md:1)

Canonical design language:

- midnight void / luminous navy background
- moon-silver typography and canopy glow
- cyan witness light for selection, progress, and active authority
- crowned tree seal as the sovereign sigil
- ceremonial phrases rather than commodity distro wording

Core palette:

- `#02050b` void
- `#071426` navy
- `#dce8ee` silver
- `#63e6ff` witness cyan
- `#19bfaf` teal
- `#2bd786` grantable green
- `#f0a53b` escalatory amber
- `#d84146` dissonant crimson

## GRUB Direction

Intent:

- present a still ceremonial chamber, not a busy animation
- keep menu readability first
- use the wallpaper as atmosphere and the seal as heraldry
- keep copy minimal and solemn

Applied text:

- `ARDA OS`
- `LAW OF THE SUBSTRATE`
- `Nothing manifests without lawful authority.`

Theme artifact:

- [arda_os/deploy/boot/themes/arda-grub/theme.txt](/home/byron/Integritas-Mechanicus/arda_os/deploy/boot/themes/arda-grub/theme.txt:1)
- now includes the silver crown-bar ornament as a ceremonial header flourish
- corrected to avoid missing pixmap-style assets during GRUB parsing

Selected default background:

- [arda_os/deploy/boot/assets/arda-ceremonial-chamber.png](/home/byron/Integritas-Mechanicus/arda_os/deploy/boot/assets/arda-ceremonial-chamber.png)
  - source: `ChatGPT Image Jul 24, 2026, 03_33_56 PM.png`
  - why: wide ceremonial chamber composition, strong central axis, and enough negative space for GRUB text without fighting the art

## Plymouth Direction

Intent:

- continue the same visual field during kernel and initramfs transition
- center the seal as the witnessing sigil
- use a single cyan progress line instead of spinners and generic dots
- keep status language in Arda voice

Theme artifacts:

- [arda_os/deploy/boot/themes/arda-plymouth/arda.plymouth](/home/byron/Integritas-Mechanicus/arda_os/deploy/boot/themes/arda-plymouth/arda.plymouth:1)
- [arda_os/deploy/boot/themes/arda-plymouth/arda.script](/home/byron/Integritas-Mechanicus/arda_os/deploy/boot/themes/arda-plymouth/arda.script:1)
- alternate mirror-gate variant:
  - [arda_os/deploy/boot/themes/arda-plymouth-mirror/arda-mirror.plymouth](/home/byron/Integritas-Mechanicus/arda_os/deploy/boot/themes/arda-plymouth-mirror/arda-mirror.plymouth:1)
  - [arda_os/deploy/boot/themes/arda-plymouth-mirror/arda-mirror.script](/home/byron/Integritas-Mechanicus/arda_os/deploy/boot/themes/arda-plymouth-mirror/arda-mirror.script:1)
  - installer now ships both `arda-mirror-gate.plymouth` and the `arda-mirror` alias path so `plymouth-set-default-theme` can resolve either name cleanly

## Asset Pack

Staged assets:

- [arda_os/deploy/boot/assets/arda-wallpaper.png](/home/byron/Integritas-Mechanicus/arda_os/deploy/boot/assets/arda-wallpaper.png)
- [arda_os/deploy/boot/assets/arda-seal.png](/home/byron/Integritas-Mechanicus/arda_os/deploy/boot/assets/arda-seal.png)
- [arda_os/deploy/boot/assets/arda-favicon.png](/home/byron/Integritas-Mechanicus/arda_os/deploy/boot/assets/arda-favicon.png)
- [arda_os/deploy/boot/assets/arda-ceremonial-chamber.png](/home/byron/Integritas-Mechanicus/arda_os/deploy/boot/assets/arda-ceremonial-chamber.png)
- [arda_os/deploy/boot/assets/arda-silver-crown-bar.png](/home/byron/Integritas-Mechanicus/arda_os/deploy/boot/assets/arda-silver-crown-bar.png)
- [arda_os/deploy/boot/assets/arda-mirror-gate.png](/home/byron/Integritas-Mechanicus/arda_os/deploy/boot/assets/arda-mirror-gate.png)

Secondary asset roles:

- `arda-silver-crown-bar.png`
  - best used as a GRUB top flourish or a login-manager ornament, not as a full background
- `arda-mirror-gate.png`
  - now promoted into the alternate Mirror Gate Plymouth composition

## Next Enhancements

- produce a cleaner dedicated 16:9 boot wallpaper without oversized `ARDA OS` lettering if you want a more austere firmware look
- render a larger high-resolution transparent seal specifically for Plymouth center-stage use
- add GRUB submenu styling for recovery and measured boot entries using grantable / escalatory / dissonant state colors
- add a post-boot display-manager theme so the handoff from Plymouth to login remains continuous
- optionally build a second Plymouth variant that uses the mirror-gate frame with a centered witness progress line
- optionally carry the crown-bar ornament forward into the future display-manager greeter
