import { TomTomConfig } from "@tomtom-org/maps-sdk/core"
import { setWorkerUrl } from "maplibre-gl"
import workerUrl from "maplibre-gl/dist/maplibre-gl-worker.mjs?worker&url"

setWorkerUrl(workerUrl)

TomTomConfig.instance.put({
  apiKey: import.meta.env.VITE_TOMTOM_API_KEY,
  language: "en-GB",
})
