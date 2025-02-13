CREATE TABLE IF NOT EXISTS employees (
    tg_id INT PRIMARY KEY,
    name VARCHAR(64) NOT NULL,
    job VARCHAR(64) NOT NULL,
    status VARCHAR(64) NOT NULL CHECK(status IN ('approved', 'pending'))
);

CREATE TABLE IF NOT EXISTS batches (
    batch_id INTEGER PRIMARY KEY AUTOINCREMENT,
    project_nm VARCHAR(64),
    product_nm VARCHAR(64),
    color VARCHAR(64),
    size VARCHAR(64),
    quantity INT,
    parts_count INT,
    cutter_id INT REFERENCES employees(tg_id),
    seamstress_id INT REFERENCES employees(tg_id),
    controller_id INT REFERENCES employees(tg_id),
    status VARCHAR(64),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    sew_start_dttm TIMESTAMP,
    sew_end_dttm TIMESTAMP
);

CREATE TABLE IF NOT EXISTS remakes (
    remake_id INTEGER PRIMARY KEY AUTOINCREMENT,
    equipment_nm VARCHAR(64) NOT NULL,
    description VARCHAR(255) NOT NULL,
    applicant_id INT REFERENCES employees(tg_id),
    remake_status VARCHAR(64) NOT NULL,
    request_dttm TIMESTAMP,
    remake_end_dttm TIMESTAMP
);


