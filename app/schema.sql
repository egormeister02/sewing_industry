CREATE TABLE IF NOT EXISTS employees (
    tg_id INT PRIMARY KEY,
    name VARCHAR(64) NOT NULL,
    job VARCHAR(64) NOT NULL CHECK(job IN ('менеджер', 'швея', 'раскройщик', 'контролер ОТК')),
    status VARCHAR(64) NOT NULL CHECK(status IN ('одобрено', 'ожидает подтверждения'))
);

CREATE TABLE IF NOT EXISTS employees_audit (
    audit_id INTEGER PRIMARY KEY AUTOINCREMENT,
    tg_id INT,
    name VARCHAR(64) NOT NULL,
    job VARCHAR(64) NOT NULL,
    status VARCHAR(64) NOT NULL,
    action_type VARCHAR(10) NOT NULL CHECK(action_type IN ('INSERT', 'UPDATE', 'DELETE')),
    action_timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS batches (
    batch_id INTEGER PRIMARY KEY AUTOINCREMENT,
    project_nm VARCHAR(64),
    product_nm VARCHAR(64),
    color VARCHAR(64),
    size VARCHAR(64),
    quantity INT,
    parts_count INT,
    cutter_id INT,
    seamstress_id INT,
    controller_id INT,
    status VARCHAR(64) NOT NULL CHECK(status IN    ('создана',
                                                    'шьется',
                                                    'пошита',
                                                    'готово',
                                                    'брак на переделке',
                                                    'переделка начата',
                                                    'переделка завершена',
                                                    'неисправимый брак')),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    sew_start_dttm TIMESTAMP,
    sew_end_dttm TIMESTAMP,
    control_dttm TIMESTAMP,

    FOREIGN KEY(seamstress_id) REFERENCES employees(tg_id),
    FOREIGN KEY(controller_id) REFERENCES employees(tg_id),
    FOREIGN KEY(cutter_id) REFERENCES employees(tg_id)
);

CREATE TABLE IF NOT EXISTS remakes (
    remake_id INTEGER PRIMARY KEY AUTOINCREMENT,
    equipment_nm VARCHAR(64) NOT NULL,
    description VARCHAR(255) NOT NULL,
    applicant_id INT REFERENCES employees(tg_id),
    status VARCHAR(64) NOT NULL CHECK(status IN ('создана', 'в работе', 'завершена')),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    remake_end_dttm TIMESTAMP
);

CREATE TABLE IF NOT EXISTS batches_audit (
    audit_id INTEGER PRIMARY KEY AUTOINCREMENT,
    batch_id INT,
    project_nm VARCHAR(64),
    product_nm VARCHAR(64),
    color VARCHAR(64),
    size VARCHAR(64),
    quantity INT,
    parts_count INT,
    cutter_id INT,
    seamstress_id INT,
    controller_id INT,
    status VARCHAR(64),
    action_type VARCHAR(10) NOT NULL CHECK(action_type IN ('INSERT', 'UPDATE', 'DELETE')),
    action_timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS remakes_audit (
    audit_id INTEGER PRIMARY KEY AUTOINCREMENT,
    remake_id INT,
    equipment_nm VARCHAR(64),
    description VARCHAR(255),
    applicant_id INT,
    status VARCHAR(64),
    action_type VARCHAR(10) NOT NULL CHECK(action_type IN ('INSERT', 'UPDATE', 'DELETE')),
    action_timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TRIGGER IF NOT EXISTS log_employee_insert
AFTER INSERT ON employees
BEGIN
    INSERT INTO employees_audit (tg_id, name, job, status, action_type)
    VALUES (NEW.tg_id, NEW.name, NEW.job, NEW.status, 'INSERT');
END;

CREATE TRIGGER IF NOT EXISTS log_employee_update
AFTER UPDATE ON employees
BEGIN
    INSERT INTO employees_audit (tg_id, name, job, status, action_type)
    VALUES (NEW.tg_id, NEW.name, NEW.job, NEW.status, 'UPDATE');
END;

CREATE TRIGGER IF NOT EXISTS log_employee_delete
AFTER DELETE ON employees
BEGIN
    INSERT INTO employees_audit (tg_id, name, job, status, action_type)
    VALUES (OLD.tg_id, OLD.name, OLD.job, OLD.status, 'DELETE');
END;

CREATE TRIGGER IF NOT EXISTS log_batch_insert
AFTER INSERT ON batches
BEGIN
    INSERT INTO batches_audit (batch_id, project_nm, product_nm, color, size, quantity, parts_count, cutter_id, seamstress_id, controller_id, status, action_type)
    VALUES (NEW.batch_id, NEW.project_nm, NEW.product_nm, NEW.color, NEW.size, NEW.quantity, NEW.parts_count, NEW.cutter_id, NEW.seamstress_id, NEW.controller_id, NEW.status, 'INSERT');
END;

CREATE TRIGGER IF NOT EXISTS log_batch_update
AFTER UPDATE ON batches
BEGIN
    INSERT INTO batches_audit (batch_id, project_nm, product_nm, color, size, quantity, parts_count, cutter_id, seamstress_id, controller_id, status, action_type)
    VALUES (NEW.batch_id, NEW.project_nm, NEW.product_nm, NEW.color, NEW.size, NEW.quantity, NEW.parts_count, NEW.cutter_id, NEW.seamstress_id, NEW.controller_id, NEW.status, 'UPDATE');
END;

CREATE TRIGGER IF NOT EXISTS log_batch_delete
AFTER DELETE ON batches
BEGIN
    INSERT INTO batches_audit (batch_id, project_nm, product_nm, color, size, quantity, parts_count, cutter_id, seamstress_id, controller_id, status, action_type)
    VALUES (OLD.batch_id, OLD.project_nm, OLD.product_nm, OLD.color, OLD.size, OLD.quantity, OLD.parts_count, OLD.cutter_id, OLD.seamstress_id, OLD.controller_id, OLD.status, 'DELETE');
END;

CREATE TRIGGER IF NOT EXISTS log_remake_insert
AFTER INSERT ON remakes
BEGIN
    INSERT INTO remakes_audit (remake_id, equipment_nm, description, applicant_id, status, action_type)
    VALUES (NEW.remake_id, NEW.equipment_nm, NEW.description, NEW.applicant_id, NEW.status, 'INSERT');
END;

CREATE TRIGGER IF NOT EXISTS log_remake_update
AFTER UPDATE ON remakes
BEGIN
    INSERT INTO remakes_audit (remake_id, equipment_nm, description, applicant_id, status, action_type)
    VALUES (NEW.remake_id, NEW.equipment_nm, NEW.description, NEW.applicant_id, NEW.status, 'UPDATE');
END;

CREATE TRIGGER IF NOT EXISTS log_remake_delete
AFTER DELETE ON remakes
BEGIN
    INSERT INTO remakes_audit (remake_id, equipment_nm, description, applicant_id, status, action_type)
    VALUES (OLD.remake_id, OLD.equipment_nm, OLD.description, OLD.applicant_id, OLD.status, 'DELETE');
END;


