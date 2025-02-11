CREATE TABLE IF NOT EXISTS products (
    product_id SERIAL PRIMARY KEY,
    name VARCHAR(255),
    parts_number VARCHAR(255),
    product_cost DECIMAL(10, 2),
    detail_payment DECIMAL(10, 2)
);

CREATE TABLE IF NOT EXISTS employees (
    employee_id SERIAL PRIMARY KEY,
    tg_id INT,
    name VARCHAR(255),
    job VARCHAR(255),
    phone_number VARCHAR(20)
);

CREATE TABLE IF NOT EXISTS pack (
    pack_id SERIAL PRIMARY KEY,
    project_nm VARCHAR(255),
    product_id INT REFERENCES products(product_id),
    color VARCHAR(50),
    size VARCHAR(50),
    cutter_id INT REFERENCES employees(employee_id),
    seamstress_id INT REFERENCES employees(employee_id),
    status VARCHAR(50),
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
    remake_id SERIAL PRIMARY KEY,
    pack_id INT REFERENCES pack(pack_id),
    remake_status VARCHAR(50),
    remake_start_dttm TIMESTAMP,
    remake_end_dttm TIMESTAMP
);


