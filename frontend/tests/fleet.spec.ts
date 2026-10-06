import { expect, test } from "@playwright/test"
import { randomVehicleName, randomVehicleUnitNumber } from "./utils/random"

test("Fleet page is accessible and shows correct title", async ({ page }) => {
  await page.goto("/fleet")
  await expect(page.getByRole("heading", { name: "Fleet" })).toBeVisible()
  await expect(
    page.getByText(
      "Add, review, update and remove vehicles in the Vector8 fleet.",
    ),
  ).toBeVisible()
})

test("Add Vehicle button is visible", async ({ page }) => {
  await page.goto("/fleet")
  await expect(page.getByRole("button", { name: "Add Vehicle" })).toBeVisible()
})

const fillRequiredFields = async (
  page: import("@playwright/test").Page,
  name: string,
  unitNumber: string,
) => {
  await page.getByLabel("Name *", { exact: true }).fill(name)
  await page.getByLabel("Unit Number *", { exact: true }).fill(unitNumber)
  await page
    .getByLabel("Profile Name *", { exact: true })
    .fill("Standard Diesel")
  await page.getByLabel("Tank Capacity (gal) *", { exact: true }).fill("150")
  await page.getByLabel("Consumption (MPG) *", { exact: true }).fill("6.8")
}

test.describe("Fleet management", () => {
  test("Create a new vehicle successfully", async ({ page }) => {
    const name = randomVehicleName()
    const unitNumber = randomVehicleUnitNumber()

    await page.goto("/fleet")
    await page.getByRole("button", { name: "Add Vehicle" }).click()
    await fillRequiredFields(page, name, unitNumber)
    await page.getByRole("button", { name: "Save" }).click()

    await expect(page.getByText("Vehicle created successfully")).toBeVisible()
    await expect(page.getByText(name)).toBeVisible()
  })

  test("Cancel vehicle creation", async ({ page }) => {
    await page.goto("/fleet")
    await page.getByRole("button", { name: "Add Vehicle" }).click()
    await page.getByLabel("Name *", { exact: true }).fill("Test Vehicle")
    await page.getByRole("button", { name: "Cancel" }).click()

    await expect(page.getByRole("dialog")).not.toBeVisible()
  })

  test("Name is required", async ({ page }) => {
    await page.goto("/fleet")
    await page.getByRole("button", { name: "Add Vehicle" }).click()
    await page.getByLabel("Name *", { exact: true }).fill("")
    await page.getByLabel("Name *", { exact: true }).blur()

    await expect(page.getByText("Name is required")).toBeVisible()
  })

  test.describe("Edit and Delete", () => {
    let vehicleName: string

    test.beforeEach(async ({ page }) => {
      vehicleName = randomVehicleName()
      const unitNumber = randomVehicleUnitNumber()

      await page.goto("/fleet")
      await page.getByRole("button", { name: "Add Vehicle" }).click()
      await fillRequiredFields(page, vehicleName, unitNumber)
      await page.getByRole("button", { name: "Save" }).click()
      await expect(page.getByText("Vehicle created successfully")).toBeVisible()
      await expect(page.getByRole("dialog")).not.toBeVisible()
    })

    test("Edit a vehicle successfully", async ({ page }) => {
      const vehicleRow = page.getByRole("row").filter({ hasText: vehicleName })
      await vehicleRow.getByRole("button").last().click()
      await page.getByRole("menuitem", { name: "Edit Vehicle" }).click()

      const updatedName = randomVehicleName()
      await page.getByLabel("Name *", { exact: true }).fill(updatedName)
      await page.getByRole("button", { name: "Save" }).click()

      await expect(page.getByText("Vehicle updated successfully")).toBeVisible()
      await expect(page.getByText(updatedName)).toBeVisible()
    })

    test("Delete a vehicle successfully", async ({ page }) => {
      const vehicleRow = page.getByRole("row").filter({ hasText: vehicleName })
      await vehicleRow.getByRole("button").last().click()
      await page.getByRole("menuitem", { name: "Delete Vehicle" }).click()

      await page.getByRole("button", { name: "Delete" }).click()

      await expect(
        page.getByText("The vehicle was deleted successfully"),
      ).toBeVisible()
      await expect(page.getByText(vehicleName)).not.toBeVisible()
    })
  })
})
