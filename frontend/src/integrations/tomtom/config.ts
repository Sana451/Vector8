import { TomTomConfig } from "@tomtom-org/maps-sdk/core"

TomTomConfig.instance.put({
  apiKey: import.meta.env.VITE_TOMTOM_API_KEY,
  language: "en-GB",
})
