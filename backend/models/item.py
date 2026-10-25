class Item:
    def __init__(
        self,
        itemId: int,
        name: str,
        description: str,
        price: float,
        category: str = "",
        brand: str = "",
        stockQuantity: int | None = None,
    ) -> None:
        self.itemId = itemId
        self.name = name
        self.description = description
        self.price = price
        self.category = category
        self.brand = brand
        # None means stock is not tracked (for example, a service).
        self.stockQuantity = stockQuantity

    def getPrice(self) -> float:
        return self.price

    def checkStock(self) -> int | None:
        return self.stockQuantity
