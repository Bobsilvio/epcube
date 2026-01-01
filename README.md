[![Sample](https://storage.ko-fi.com/cdn/generated/zfskfgqnf/2025-03-07_rest-7d81acd901abf101cbdf54443c38f6f0-dlmmonph.jpg)](https://ko-fi.com/silviosmart)

# EP Cube Integration for Home Assistant

Custom Home Assistant integration for monitoring the EP Cube energy storage system using the **unofficial API** (the same used by the official iOS/Android apps).

---

## 🔧 Features

- 📡 **Live data** updates every 5 seconds  
- 📊 Access to **monthly, weekly, and yearly statistics**  
  - Disabled by default to reduce load  
  - Can be enabled individually or all at once via configuration  
- ⚙️ Built-in **configuration and diagnostic entities**  
- 🧩 Fully integrated with Home Assistant UI (config flow, device info, icons)
- 🔐 Requires a **valid Bearer token** (token generation via reverse engineering, [HERE](https://epcube-token.streamlit.app/))

---

## 📦 Installation via HACS

1. Open Home Assistant  
2. Go to **HACS > Integrations > Custom repositories**  
3. Add: `https://github.com/Bobsilvio/epcube` with type `Integration`  
4. Search for `EPCube` and install it  
5. Restart Home Assistant  
6. Go to **Settings > Devices & Services** and add the integration

## 📦 Installation simple
[![Open in HACS](https://my.home-assistant.io/badges/hacs_repository.svg)](https://my.home-assistant.io/redirect/hacs_repository/?owner=bobsilvio&repository=epcube&category=integration)

---

## ⚠️ Requirements

- EP Cube account  
- Bearer token ([HERE](https://github.com/Bobsilvio/epcube-token))

---

## 📜 Disclaimer

This project is not affiliated with or endorsed by EP Cube or Canadian Solar.  
Use at your own risk. The API used is not officially documented or supported.
