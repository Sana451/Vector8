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

test("Add Vehicle link is visible", async ({ page }) => {
  await page.goto("/fleet")
  await expect(page.getByRole("link", { name: "Add Vehicle" })).toBeVisible()
})

const openNewVehiclePage = async (page: import("@playwright/test").Page) => {
  await page.goto("/fleet")
  await page.getByRole("link", { name: "Add Vehicle" }).click()
  await expect(page).toHaveURL(/\/fleet\/new$/)
  await expect(page.getByRole("heading", { name: "Add vehicle" })).toBeVisible()
}

const fillRequiredFields = async (
  page: import("@playwright/test").Page,
  name: string,
  unitNumber: string,
) => {
  await page.getByLabel("Name *", { exact: true }).fill(name)
  await page.getByLabel("Unit Number *", { exact: true }).fill(unitNumber)
  await page.getByLabel("Tank Capacity (gal) *", { exact: true }).fill("150")
  await page.getByLabel("Consumption (MPG) *", { exact: true }).fill("6.8")
}

test.describe("Fleet management", () => {
  test("Create a new vehicle successfully", async ({ page }) => {
    const name = randomVehicleName()
    const unitNumber = randomVehicleUnitNumber()

    await openNewVehiclePage(page)
    await fillRequiredFields(page, name, unitNumber)
    await page.getByRole("button", { name: "Save" }).click()

    await expect(page).toHaveURL(/\/fleet$/)
    await expect(page.getByText("Vehicle created successfully")).toBeVisible()
    await expect(page.getByRole("row").filter({ hasText: name })).toBeVisible()
  })

  test("Cancel vehicle creation", async ({ page }) => {
    await openNewVehiclePage(page)
    await page.getByLabel("Name *", { exact: true }).fill("Test Vehicle")
    await page.getByRole("button", { name: "Cancel" }).click()

    await expect(page).toHaveURL(/\/fleet$/)
    await expect(page.getByRole("heading", { name: "Fleet" })).toBeVisible()
  })

  test("Name is required", async ({ page }) => {
    await openNewVehiclePage(page)
    await page.getByLabel("Name *", { exact: true }).fill("")
    await page.getByLabel("Name *", { exact: true }).blur()

    await expect(page.getByText("Name is required")).toBeVisible()
  })

  test.describe("Edit and Delete", () => {
    let vehicleName: string

    test.beforeEach(async ({ page }) => {
      vehicleName = randomVehicleName()
      const unitNumber = randomVehicleUnitNumber()

      await openNewVehiclePage(page)
      await fillRequiredFields(page, vehicleName, unitNumber)
      await page.getByRole("button", { name: "Save" }).click()
      await expect(page).toHaveURL(/\/fleet$/)
      await expect(page.getByText("Vehicle created successfully")).toBeVisible()
      await expect(
        page.getByRole("row").filter({ hasText: vehicleName }),
      ).toBeVisible()
    })

    test("Edit a vehicle successfully", async ({ page }) => {
      const vehicleRow = page.getByRole("row").filter({ hasText: vehicleName })
      await vehicleRow.click()
      await expect(page).toHaveURL(/\/fleet\/[^/]+$/)
      await page.getByRole("link", { name: "Edit" }).click()
      await expect(page).toHaveURL(/\/fleet\/[^/]+\/edit$/)

      const updatedName = randomVehicleName()
      await page.getByLabel("Name *", { exact: true }).fill(updatedName)
      await page.getByRole("button", { name: "Save" }).click()

      await expect(page).toHaveURL(/\/fleet\/[^/]+$/)
      await expect(page.getByText("Vehicle updated successfully")).toBeVisible()
      await expect(
        page.getByRole("heading", { name: new RegExp(updatedName) }),
      ).toBeVisible()
    })

    test("Delete a vehicle successfully", async ({ page }) => {
      const vehicleRow = page.getByRole("row").filter({ hasText: vehicleName })
      await vehicleRow.click()
      await expect(page).toHaveURL(/\/fleet\/[^/]+$/)
      await page.getByRole("button", { name: "Delete", exact: true }).click()

      const dialog = page.getByRole("dialog")
      await expect(dialog).toBeVisible()
      await dialog.getByRole("button", { name: "Delete" }).click()

      await expect(page).toHaveURL(/\/fleet$/)
      await expect(
        page.getByText("The vehicle was deleted successfully"),
      ).toBeVisible()
      await expect(page.getByText(vehicleName)).not.toBeVisible()
    })
  })
})
