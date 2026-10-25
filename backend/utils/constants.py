class DatabaseTables:
    ADMIN = "admin"
    CUSTOMER = "customer"
    EVENT = "event"
    EVENT_REGISTRATION = "event_registration"
    APPOINTMENT = "appointment"
    ORDERS = "orders"
    ITEM = "item"
    SHOPPING_CART = "shopping_cart"
    ORDER_ITEM = "order_item"
    PAYMENT = "payment"
    STATUS = "status"


class DatabaseColumns:
    CUSTOMER_ID = "customer_id"
    EVENT_ID = "event_id"
    APPOINTMENT_ID = "appointment_id"
    ORDER_ID = "order_id"
    ITEM_ID = "item_id"
    PAYMENT_ID = "payment_id"
    ADMIN_ID = "admin_id"
    NAME = "name"
    EMAIL = "email"
    PHONE = "phone"
    ADDRESS = "address"
    PASSWORD_HASH = "password_hash"
    DESCRIPTION = "description"
    LOCATION = "location"
    EVENT_DATE_TIME = "eventDateTime"
    PARTICIPANT_LIMIT = "participantLimit"
    STATUS_ID = "statusID"
    APPOINTMENT_TIME = "appointmentTime"
    ORDER_DATE_TIME = "orderDateTime"
    TOTAL_AMOUNT = "totalAmount"
    PRICE = "price"
    CATEGORY = "category"
    BRAND = "brand"
    STOCK_QUANTITY = "stock_quantity"
    ITEMS_JSON = "items_json"
    QUANTITY = "quantity"
    UNIT_PRICE = "unit_price"
    PAYMENT_DATE_TIME = "paymentDateTime"
    PAYMENT_METHOD = "paymentMethod"
    PAYMENT_STATUS_ID = "statusID"
    AMOUNT = "amount"
    UPDATED_AT = "updated_at"


class DatabaseValues:
    ORDER_STATUS_ID_PENDING = 7
    PAYMENT_STATUS_ID_PAID = 11


DATABASE_SCHEMA_COLUMNS = {
    DatabaseTables.ADMIN: (
        DatabaseColumns.ADMIN_ID,
        DatabaseColumns.NAME,
        DatabaseColumns.EMAIL,
        DatabaseColumns.PHONE,
        DatabaseColumns.ADDRESS,
        DatabaseColumns.PASSWORD_HASH,
    ),
    DatabaseTables.CUSTOMER: (
        DatabaseColumns.CUSTOMER_ID,
        DatabaseColumns.NAME,
        DatabaseColumns.EMAIL,
        DatabaseColumns.PHONE,
        DatabaseColumns.ADDRESS,
        DatabaseColumns.PASSWORD_HASH,
    ),
    DatabaseTables.EVENT: (
        DatabaseColumns.EVENT_ID,
        DatabaseColumns.ADMIN_ID,
        DatabaseColumns.LOCATION,
        DatabaseColumns.NAME,
        DatabaseColumns.DESCRIPTION,
        DatabaseColumns.EVENT_DATE_TIME,
        DatabaseColumns.PARTICIPANT_LIMIT,
        DatabaseColumns.STATUS_ID,
        DatabaseColumns.CATEGORY,
    ),
    DatabaseTables.EVENT_REGISTRATION: (
        DatabaseColumns.EVENT_ID,
        DatabaseColumns.CUSTOMER_ID,
    ),
    DatabaseTables.APPOINTMENT: (
        DatabaseColumns.APPOINTMENT_ID,
        DatabaseColumns.CUSTOMER_ID,
        DatabaseColumns.APPOINTMENT_TIME,
        DatabaseColumns.DESCRIPTION,
        DatabaseColumns.STATUS_ID,
        DatabaseColumns.CATEGORY,
    ),
    DatabaseTables.ORDERS: (
        DatabaseColumns.ORDER_ID,
        DatabaseColumns.CUSTOMER_ID,
        DatabaseColumns.ORDER_DATE_TIME,
        DatabaseColumns.TOTAL_AMOUNT,
        DatabaseColumns.STATUS_ID,
        DatabaseColumns.CATEGORY,
    ),
    DatabaseTables.ITEM: (
        DatabaseColumns.ITEM_ID,
        DatabaseColumns.NAME,
        DatabaseColumns.DESCRIPTION,
        DatabaseColumns.PRICE,
        DatabaseColumns.CATEGORY,
        DatabaseColumns.BRAND,
        DatabaseColumns.STOCK_QUANTITY,
    ),
    DatabaseTables.SHOPPING_CART: (
        DatabaseColumns.CUSTOMER_ID,
        DatabaseColumns.ITEMS_JSON,
        DatabaseColumns.UPDATED_AT,
    ),
    DatabaseTables.ORDER_ITEM: (
        DatabaseColumns.ORDER_ID,
        DatabaseColumns.ITEM_ID,
        DatabaseColumns.QUANTITY,
        DatabaseColumns.UNIT_PRICE,
    ),
    DatabaseTables.PAYMENT: (
        DatabaseColumns.PAYMENT_ID,
        DatabaseColumns.ORDER_ID,
        DatabaseColumns.PAYMENT_DATE_TIME,
        DatabaseColumns.AMOUNT,
        DatabaseColumns.PAYMENT_METHOD,
        DatabaseColumns.PAYMENT_STATUS_ID,
        DatabaseColumns.CATEGORY,
    ),
    DatabaseTables.STATUS: (
        DatabaseColumns.STATUS_ID,
        DatabaseColumns.CATEGORY,
        DatabaseColumns.NAME,
    ),
}
