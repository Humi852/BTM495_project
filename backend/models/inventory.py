from backend.models.part import Part
from backend.utils.response import Response


class Inventory:
    def __init__(self, inventoryId: int) -> None:
        self.inventoryId = inventoryId
        self.items: dict[int, Part] = {}

    def addItem(self, part: Part) -> Response:
        if part.itemId in self.items:
            return Response.warning("Item already exists.")
        self.items[part.itemId] = part
        return Response.ok("Item added successfully.", part)

    def updateItem(self, itemId: int, quantity: int) -> Response:
        if itemId not in self.items or type(quantity) is not int or quantity < 0:
            return Response.warning("Invalid item or quantity.")
        self.items[itemId].stockQuantity = quantity
        return Response.ok("Item updated successfully.", self.items[itemId])

    def markOutOfStock(self, itemId: int) -> Response:
        return self.updateItem(itemId, 0)

    def checkStock(self, itemId: int) -> Response:
        if itemId not in self.items:
            return Response.warning("Item not found.")
        return Response.ok("Stock retrieved.", self.items[itemId].checkStock())
