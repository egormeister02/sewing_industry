COLUMN_TRANSLATIONS = {
    'employees': {
        'tg_id': 'ID сотрудника',
        'name': 'ФИО',
        'job': 'Должность',
        'status': 'Статус'
    },
    'batches': {
        'batch_id': 'ID пачки',
        'project_nm': 'Наименование проекта',
        'product_nm': 'Тип изделия',
        'color': 'Цвет',
        'size': 'Размер',
        'quantity': 'Количество',
        'parts_count': 'Количество деталей',
        'cutter_id': 'ID раскройщика',
        'seamstress_id': 'ID швеи',
        'controller_id': 'ID контролера',
        'cutter_pay': 'Оплата за деталь',
        'seamstress_pay': 'Оплата за изделие',
        'status': 'Статус',
        'type': 'Тип',
        'created_at': 'Дата создания',
        'sew_start_dttm': 'Дата начала шитья',
        'sew_end_dttm': 'Дата окончания шитья',
        'control_dttm': 'Дата контроля',
        
    },
    'remakes': {
        'remake_id': 'ID ремонта',
        'equipment_nm': 'Наименование оборудования',
        'description': 'Описание',
        'applicant_id': 'ID заявителя',
        'status': 'Статус',
        'created_at': 'Дата создания',
        'remake_end_dttm': 'Дата окончания ремонта'
    },
    'payments': {
        'payment_id': 'ID выплаты',
        'employee_id': 'ID сотрудника',
        'amount': 'Сумма',
        'type': 'Тип',
        'payment_date': 'Дата выплаты'
    }
}

TABLE_TRANSLATIONS = {
    'employees': 'Сотрудники',
    'batches': 'Пачки',
    'remakes': 'Ремонты',
    'payments': 'Выплаты'
}