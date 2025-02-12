CREATE TABLE IF NOT EXISTS products (
    product_id SERIAL PRIMARY KEY,
    name VARCHAR(64),
    parts_number VARCHAR(64),
    product_cost DECIMAL(10, 2),
    detail_payment DECIMAL(10, 2)
);

CREATE TABLE IF NOT EXISTS employees (
    employee_id INTEGER PRIMARY KEY AUTOINCREMENT,
    tg_id INT,
    name VARCHAR(64),
    job VARCHAR(64),
    phone_number VARCHAR(20)
);

CREATE TABLE IF NOT EXISTS batches (
    batch_id INTEGER PRIMARY KEY AUTOINCREMENT,
    project_nm VARCHAR(64),
    product_nm VARCHAR(64),
    color VARCHAR(64),
    size VARCHAR(64),
    quantity INT,
    parts_count INT,
    cutter_id INT REFERENCES employees(employee_id),
    seamstress_id INT REFERENCES employees(employee_id),
    controller_id INT REFERENCES employees(employee_id),
    status VARCHAR(64),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    sew_start_dttm TIMESTAMP,
    sew_end_dttm TIMESTAMP
);

CREATE TABLE IF NOT EXISTS salary (
    employee_id INT REFERENCES employees(employee_id),
    pack_id INT REFERENCES pack(pack_id),
    money DECIMAL(10, 2),
    datetime TIMESTAMP,
    PRIMARY KEY (employee_id, pack_id)
);

CREATE TABLE IF NOT EXISTS remakes (
    remake_id INTEGER PRIMARY KEY AUTOINCREMENT,
    equipment_nm VARCHAR(64),
    description VARCHAR(255),
    applicant_id INT REFERENCES employees(employee_id),
    remake_status VARCHAR(64),
    request_dttm TIMESTAMP,
    remake_end_dttm TIMESTAMP
);


