CREATE TABLE IF NOT EXISTS employees (
    tg_id INTEGER PRIMARY KEY AUTOINCREMENT,
    name VARCHAR(64) NOT NULL,
    job VARCHAR(64) NOT NULL CHECK(job IN ('менеджер', 'швея', 'раскройщик', 'контролер ОТК')),
    status VARCHAR(64) NOT NULL CHECK(status IN ('одобрено', 'ожидает подтверждения'))
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
    cutter_pay INT,
    seamstress_pay INT,
    status VARCHAR(64) CHECK(status IN    ('создана',
                                                    'шьется',
                                                    'пошита',
                                                    'готово',
                                                    'брак на переделке',
                                                    'переделка начата',
                                                    'переделка завершена',
                                                    'неисправимый брак')),
    type VARCHAR(64) CHECK(type IN ('обычная', 'образец')),
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
    equipment_nm VARCHAR(64),
    description VARCHAR(255),
    applicant_id INT,
    status VARCHAR(64) CHECK(status IN ('создана', 'в работе', 'завершена')),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    remake_end_dttm TIMESTAMP,

    FOREIGN KEY(applicant_id) REFERENCES employees(tg_id)
);

CREATE TABLE IF NOT EXISTS payments (
    payment_id INTEGER PRIMARY KEY AUTOINCREMENT,
    employee_id INT,
    amount INT CHECK(amount > 0),
    type VARCHAR(64) CHECK(type IN ('зарплата', 'премия', 'штраф')),
    payment_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    FOREIGN KEY(employee_id) REFERENCES employees(tg_id)
);

CREATE VIEW IF NOT EXISTS employee_payment_info AS
SELECT 
    e.tg_id,
    e.name,
    e.job,
    COALESCE(p.total_payments, 0) AS total_payments,
    COALESCE(b.total_pay, 0) AS total_pay
FROM 
    employees e
LEFT JOIN 
    (SELECT employee_id, SUM(CASE WHEN type = 'премия' THEN -amount ELSE amount END) AS total_payments 
     FROM payments 
     GROUP BY employee_id) p ON e.tg_id = p.employee_id
LEFT JOIN 
    (SELECT 
        e.tg_id tg_id, 
        SUM(CASE WHEN e.job = 'швея' THEN b.seamstress_pay * b.quantity ELSE b.cutter_pay * b.quantity * b.parts_count END) AS total_pay 
     FROM 
        employees e
    LEFT JOIN 
        batches b ON e.tg_id = b.cutter_id OR e.tg_id = b.seamstress_id
    WHERE 
        e.job = 'раскройщик' or (e.job = 'швея' and b.status in ('готово', 'брак'))
    GROUP BY 
        e.tg_id) b ON e.tg_id = b.tg_id
WHERE 
    e.job IN ('швея', 'раскройщик');

CREATE TABLE IF NOT EXISTS employees_audit (
    audit_id INTEGER PRIMARY KEY AUTOINCREMENT,
    tg_id INT,
    name VARCHAR(64),
    job VARCHAR(64),
    status VARCHAR(64),
    action_type VARCHAR(10) NOT NULL CHECK(action_type IN ('INSERT', 'UPDATE', 'DELETE')),
    action_timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
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
    type VARCHAR(64),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    sew_start_dttm TIMESTAMP,
    sew_end_dttm TIMESTAMP,
    control_dttm TIMESTAMP,
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
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    remake_end_dttm TIMESTAMP,
    action_type VARCHAR(10) NOT NULL CHECK(action_type IN ('INSERT', 'UPDATE', 'DELETE')),
    action_timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS payments_audit (
    audit_id INTEGER PRIMARY KEY AUTOINCREMENT,
    payment_id INT,
    employee_id INT,
    amount INT,
    type VARCHAR(64),
    payment_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    action_type VARCHAR(10) NOT NULL CHECK(action_type IN ('INSERT', 'UPDATE', 'DELETE'))
);

CREATE TRIGGER IF NOT EXISTS log_payment_insert
AFTER INSERT ON payments
BEGIN
    INSERT INTO payments_audit (payment_id, employee_id, amount, type, payment_date, action_type)
    VALUES (NEW.payment_id, NEW.employee_id, NEW.amount, NEW.type, NEW.payment_date, 'INSERT');
END;

CREATE TRIGGER IF NOT EXISTS log_payment_update
AFTER UPDATE ON payments
BEGIN
    INSERT INTO payments_audit (payment_id, employee_id, amount, type, payment_date, action_type)
    VALUES (NEW.payment_id, NEW.employee_id, NEW.amount, NEW.type, NEW.payment_date, 'UPDATE');
END;

CREATE TRIGGER IF NOT EXISTS log_payment_delete
AFTER DELETE ON payments
BEGIN
    INSERT INTO payments_audit (payment_id, employee_id, amount, type, payment_date, action_type)
    VALUES (OLD.payment_id, OLD.employee_id, OLD.amount, OLD.type, OLD.payment_date, 'DELETE');
END;


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
    INSERT INTO batches_audit (batch_id, project_nm, product_nm, color, size, quantity, parts_count, cutter_id, seamstress_id, controller_id, status, type, created_at, sew_start_dttm, sew_end_dttm, control_dttm, action_type)
    VALUES (NEW.batch_id, NEW.project_nm, NEW.product_nm, NEW.color, NEW.size, NEW.quantity, NEW.parts_count, NEW.cutter_id, NEW.seamstress_id, NEW.controller_id, NEW.status, NEW.type, NEW.created_at, NEW.sew_start_dttm, NEW.sew_end_dttm, NEW.control_dttm, 'INSERT');
END;

CREATE TRIGGER IF NOT EXISTS log_batch_update
AFTER UPDATE ON batches
BEGIN
    INSERT INTO batches_audit (batch_id, project_nm, product_nm, color, size, quantity, parts_count, cutter_id, seamstress_id, controller_id, status, type, created_at, sew_start_dttm, sew_end_dttm, control_dttm, action_type)
    VALUES (NEW.batch_id, NEW.project_nm, NEW.product_nm, NEW.color, NEW.size, NEW.quantity, NEW.parts_count, NEW.cutter_id, NEW.seamstress_id, NEW.controller_id, NEW.status, NEW.type, NEW.created_at, NEW.sew_start_dttm, NEW.sew_end_dttm, NEW.control_dttm, 'UPDATE');
END;

CREATE TRIGGER IF NOT EXISTS log_batch_delete
AFTER DELETE ON batches
BEGIN
    INSERT INTO batches_audit (batch_id, project_nm, product_nm, color, size, quantity, parts_count, cutter_id, seamstress_id, controller_id, status, type, created_at, sew_start_dttm, sew_end_dttm, control_dttm, action_type)
    VALUES (OLD.batch_id, OLD.project_nm, OLD.product_nm, OLD.color, OLD.size, OLD.quantity, OLD.parts_count, OLD.cutter_id, OLD.seamstress_id, OLD.controller_id, OLD.status, OLD.type, OLD.created_at, OLD.sew_start_dttm, OLD.sew_end_dttm, OLD.control_dttm, 'DELETE');
END;

CREATE TRIGGER IF NOT EXISTS log_remake_insert
AFTER INSERT ON remakes
BEGIN
    INSERT INTO remakes_audit (remake_id, equipment_nm, description, applicant_id, status, created_at, remake_end_dttm, action_type)
    VALUES (NEW.remake_id, NEW.equipment_nm, NEW.description, NEW.applicant_id, NEW.status, NEW.created_at, NEW.remake_end_dttm, 'INSERT');
END;

CREATE TRIGGER IF NOT EXISTS log_remake_update
AFTER UPDATE ON remakes
BEGIN
    INSERT INTO remakes_audit (remake_id, equipment_nm, description, applicant_id, status, created_at, remake_end_dttm, action_type)
    VALUES (NEW.remake_id, NEW.equipment_nm, NEW.description, NEW.applicant_id, NEW.status, NEW.created_at, NEW.remake_end_dttm, 'UPDATE');
END;

CREATE TRIGGER IF NOT EXISTS log_remake_delete
AFTER DELETE ON remakes
BEGIN
    INSERT INTO remakes_audit (remake_id, equipment_nm, description, applicant_id, status, created_at, remake_end_dttm, action_type)
    VALUES (OLD.remake_id, OLD.equipment_nm, OLD.description, OLD.applicant_id, OLD.status, OLD.created_at, OLD.remake_end_dttm, 'DELETE');
END;


