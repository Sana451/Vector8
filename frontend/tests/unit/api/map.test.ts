import { afterEach, describe, expect, it, vi } from "vitest"
import { searchAddress } from "@/api/map"
import { GeocodingService } from "@/client"

afterEach(() => {
  vi.restoreAllMocks()
})

describe("searchAddress", () => {
  it("calls the geocoding endpoint with the expected payload", async () => {
    const responseBody = {
      formatted_address: "1521 Hickory Trail, Allen, TX 75002",
      location: {
        type: "Point" as const,
        coordinates: [-96.6705, 33.1032] as [number, number],
      },
    }

    const searchSpy = vi
      .spyOn(GeocodingService, "search")
      .mockResolvedValue({ data: responseBody } as Awaited<
        ReturnType<typeof GeocodingService.search>
      >)

    const result = await searchAddress("1521 Hickory Trail Allen TX 75002")

    expect(searchSpy).toHaveBeenCalledWith({
      body: { query: "1521 Hickory Trail Allen TX 75002" },
      query: { force_refresh: false },
    })
    expect(result).toEqual(responseBody)
  })
})
