-- إنشاء قاعدة البيانات
CREATE DATABASE mybookdb;
GO

USE mybookdb;
GO

-- إنشاء جدول المستخدمين
CREATE TABLE users (
    id INT IDENTITY(1,1) PRIMARY KEY,
    username NVARCHAR(255) UNIQUE NOT NULL,
    password NVARCHAR(MAX) NOT NULL,
    is_admin BIT DEFAULT 0
);
GO

-- إنشاء جدول الكتب
CREATE TABLE books (
    id INT IDENTITY(1,1) PRIMARY KEY,
    title NVARCHAR(255) NOT NULL,
    author NVARCHAR(255) NOT NULL,
    price FLOAT NOT NULL,
    cover_url NVARCHAR(512) DEFAULT NULL
);
GO

-- إنشاء جدول سلة التسوق
CREATE TABLE cart (
    id INT IDENTITY(1,1) PRIMARY KEY,
    user_id INT,
    book_id INT,
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
    FOREIGN KEY (book_id) REFERENCES books(id) ON DELETE CASCADE
);
GO

-- إنشاء جدول الطلبات
CREATE TABLE orders (
    id INT IDENTITY(1,1) PRIMARY KEY,
    user_id INT,
    order_date DATETIME DEFAULT GETDATE(),
    total_amount FLOAT NOT NULL,
    status NVARCHAR(50) DEFAULT 'pending',
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE SET NULL
);
GO

-- إنشاء جدول عناصر الطلبات
CREATE TABLE order_items (
    id INT IDENTITY(1,1) PRIMARY KEY,
    order_id INT,
    book_id INT,
    quantity INT NOT NULL DEFAULT 1,
    price FLOAT NOT NULL,
    FOREIGN KEY (order_id) REFERENCES orders(id) ON DELETE CASCADE,
    FOREIGN KEY (book_id) REFERENCES books(id) ON DELETE NO ACTION
);
GO

-- إضافة بعض البيانات الافتراضية للاختبار

-- إضافة مستخدم مسؤول
INSERT INTO users (username, password, is_admin)
VALUES ('admin', HASHBYTES('SHA2_256', 'admin123'), 1);

-- إضافة مستخدم عادي
INSERT INTO users (username, password, is_admin)
VALUES ('user', HASHBYTES('SHA2_256', 'user123'), 0);

-- إضافة بعض الكتب
INSERT INTO books (title, author, price, cover_url)
VALUES
('Life Of Secrets', 'John Smith', 19.99, 'imgs/img (1).jpg'),
('Simple Way Of Peace Life', 'Sarah Johnson', 24.99, 'imgs/img (2).jpg'),
('Great Travel At Desert', 'Michael Brown', 15.99, 'imgs/img (3).jpg'),
('The Art of Programming', 'Jane Doe', 29.99, 'imgs/img (4).jpg'),
('History of Ancient Egypt', 'Robert Wilson', 22.99, 'imgs/img (5).jpg');

-- إضافة بعض العناصر إلى سلة التسوق
INSERT INTO cart (user_id, book_id)
VALUES
(2, 1),  -- المستخدم العادي لديه الكتاب الأول في سلة التسوق
(2, 3);  -- المستخدم العادي لديه الكتاب الثالث في سلة التسوق
GO

-- استعلام لعرض الكتب في سلة التسوق لمستخدم معين
CREATE PROCEDURE GetUserCart
    @UserId INT
AS
BEGIN
    SELECT b.id, b.title, b.author, b.price, b.cover_url
    FROM cart c
    JOIN books b ON c.book_id = b.id
    WHERE c.user_id = @UserId;
END;
GO

-- استعلام لإضافة كتاب إلى سلة التسوق
CREATE PROCEDURE AddToCart
    @UserId INT,
    @BookId INT
AS
BEGIN
    INSERT INTO cart (user_id, book_id)
    VALUES (@UserId, @BookId);
END;
GO

-- استعلام لحذف كتاب من سلة التسوق
CREATE PROCEDURE RemoveFromCart
    @UserId INT,
    @BookId INT
AS
BEGIN
    DELETE FROM cart
    WHERE user_id = @UserId AND book_id = @BookId;
END;
GO

-- استعلام لتفريغ سلة التسوق لمستخدم معين
CREATE PROCEDURE ClearCart
    @UserId INT
AS
BEGIN
    DELETE FROM cart
    WHERE user_id = @UserId;
END;
GO

-- استعلام لإنشاء طلب جديد من سلة التسوق
CREATE PROCEDURE CreateOrderFromCart
    @UserId INT
AS
BEGIN
    DECLARE @OrderId INT;
    DECLARE @TotalAmount FLOAT;

    -- حساب المبلغ الإجمالي من سلة التسوق
    SELECT @TotalAmount = SUM(b.price)
    FROM cart c
    JOIN books b ON c.book_id = b.id
    WHERE c.user_id = @UserId;

    -- إذا كانت السلة فارغة، لا تقم بإنشاء طلب
    IF @TotalAmount IS NULL OR @TotalAmount = 0
    BEGIN
        RETURN;
    END;

    -- إنشاء طلب جديد
    INSERT INTO orders (user_id, total_amount, status)
    VALUES (@UserId, @TotalAmount, 'pending');

    -- الحصول على معرف الطلب الجديد
    SET @OrderId = SCOPE_IDENTITY();

    -- نقل العناصر من سلة التسوق إلى عناصر الطلب
    INSERT INTO order_items (order_id, book_id, quantity, price)
    SELECT @OrderId, c.book_id, 1, b.price
    FROM cart c
    JOIN books b ON c.book_id = b.id
    WHERE c.user_id = @UserId;

    -- تفريغ سلة التسوق
    DELETE FROM cart
    WHERE user_id = @UserId;
END;
GO

-- استعلام لتحديث حالة الطلب
CREATE PROCEDURE UpdateOrderStatus
    @OrderId INT,
    @Status NVARCHAR(50)
AS
BEGIN
    UPDATE orders
    SET status = @Status
    WHERE id = @OrderId;
END;
GO

-- استعلام للحصول على تفاصيل الطلب
CREATE PROCEDURE GetOrderDetails
    @OrderId INT
AS
BEGIN
    -- معلومات الطلب الرئيسية
    SELECT o.id, o.order_date, o.total_amount, o.status, u.username
    FROM orders o
    LEFT JOIN users u ON o.user_id = u.id
    WHERE o.id = @OrderId;

    -- عناصر الطلب
    SELECT oi.id, b.title, b.author, oi.quantity, oi.price, (oi.quantity * oi.price) AS item_total
    FROM order_items oi
    JOIN books b ON oi.book_id = b.id
    WHERE oi.order_id = @OrderId;
END;
GO

-- استعلام للحصول على جميع طلبات المستخدم
CREATE PROCEDURE GetUserOrders
    @UserId INT
AS
BEGIN
    SELECT id, order_date, total_amount, status
    FROM orders
    WHERE user_id = @UserId
    ORDER BY order_date DESC;
END;
GO
