PRAGMA foreign_keys = ON;

-- =====================================================
-- HOTEL / BUILDING / LOCATION STRUCTURE
-- =====================================================

CREATE TABLE hotel (
    hotelId INTEGER PRIMARY KEY,
    name TEXT NOT NULL
    -- example: (1, 'Last Resort Hotel')
);

CREATE TABLE building (
    buildingId INTEGER PRIMARY KEY,
    hotelId INTEGER NOT NULL,
    buildingName TEXT NOT NULL,
    FOREIGN KEY (hotelId) REFERENCES hotel(hotelId),
    UNIQUE (hotelId, buildingName)
    -- example: (1, 1, 'Main Building')
);

CREATE TABLE wing (
    wingId INTEGER PRIMARY KEY,
    buildingId INTEGER NOT NULL,
    wingCode TEXT NOT NULL,                       -- example: 'A', 'B', 'EAST'
    wingOrder INTEGER NOT NULL,                  -- example: 1, 2, 3
    nearIndoorPool INTEGER NOT NULL DEFAULT 0 CHECK (nearIndoorPool IN (0,1)),   -- 1=yes
    nearOutdoorPool INTEGER NOT NULL DEFAULT 0 CHECK (nearOutdoorPool IN (0,1)), -- 1=yes
    nearParking INTEGER NOT NULL DEFAULT 0 CHECK (nearParking IN (0,1)),         -- 1=yes
    handicapAccess INTEGER NOT NULL DEFAULT 0 CHECK (handicapAccess IN (0,1)),   -- 1=yes
    FOREIGN KEY (buildingId) REFERENCES building(buildingId),
    UNIQUE (buildingId, wingCode),               -- example: building 1, wing 'A'
    UNIQUE (buildingId, wingOrder)               -- example: building 1, first wing = 1
);

CREATE TABLE level (
    levelId INTEGER PRIMARY KEY,
    wingId INTEGER NOT NULL,
    levelNumber INTEGER NOT NULL,                -- example: 1, 2, 3
    isSmoking INTEGER NOT NULL CHECK (isSmoking IN (0,1)), -- 0=no, 1=yes
    FOREIGN KEY (wingId) REFERENCES wing(wingId),
    UNIQUE (wingId, levelNumber)
    -- example: (1, 1, 2, 0)
);

CREATE TABLE room (
    roomId INTEGER PRIMARY KEY,
    levelId INTEGER NOT NULL,
    roomNum TEXT NOT NULL,                       -- example: '205', '318', '401'
    isSmokingOverride INTEGER CHECK (isSmokingOverride IN (0,1)) DEFAULT NULL,
    FOREIGN KEY (levelId) REFERENCES level(levelId),
    UNIQUE (levelId, roomNum)
    -- example: (205, 2, '205', NULL)
);

-- =====================================================
-- ROOM CAPABILITIES / FIXTURES / BEDS / ADJACENCY
-- =====================================================

CREATE TABLE capability_type (
    capabilityTypeId INTEGER PRIMARY KEY,
    capabilityCode TEXT NOT NULL UNIQUE
    -- examples:
    -- (1, 'SLEEPING')
    -- (2, 'MEETING')
    -- (3, 'SUITE')
);

CREATE TABLE room_capability (
    roomId INTEGER NOT NULL,
    capabilityTypeId INTEGER NOT NULL,
    capacity INTEGER NOT NULL CHECK (capacity > 0),           -- sleeping guests or meeting seats
    baseRate DECIMAL(10,2) NOT NULL CHECK (baseRate >= 0),    -- example: 220.00
    isAssignable INTEGER NOT NULL DEFAULT 1 CHECK (isAssignable IN (0,1)),
    PRIMARY KEY (roomId, capabilityTypeId),
    FOREIGN KEY (roomId) REFERENCES room(roomId),
    FOREIGN KEY (capabilityTypeId) REFERENCES capability_type(capabilityTypeId)
    -- examples:
    -- (205, 1, 2, 220.00, 1)   -- room 205 can sleep 2 guests
    -- (401, 2, 60, 500.00, 1)  -- room 401 can host a meeting of 60
);

CREATE TABLE fixture_type (
    fixtureTypeId INTEGER PRIMARY KEY,
    fixtureCode TEXT NOT NULL UNIQUE
    -- examples:
    -- (1, 'TOILET_BATH')
    -- (2, 'EXTRA_MEETING_SPACE')
    -- (3, 'OUTDOOR_SPACE')
);

CREATE TABLE room_fixture (
    roomId INTEGER NOT NULL,
    fixtureTypeId INTEGER NOT NULL,
    PRIMARY KEY (roomId, fixtureTypeId),
    FOREIGN KEY (roomId) REFERENCES room(roomId),
    FOREIGN KEY (fixtureTypeId) REFERENCES fixture_type(fixtureTypeId)
    -- examples:
    -- (205, 1)
    -- (401, 2)
);

CREATE TABLE bed_type (
    bedTypeId INTEGER PRIMARY KEY,
    bedCode TEXT NOT NULL UNIQUE,               -- example: 'QUEEN_STD', 'KING_STD'
    size TEXT NOT NULL,                         -- example: 'QUEEN', 'KING', 'ROLLAWAY'
    isPermanent INTEGER NOT NULL CHECK (isPermanent IN (0,1))
    -- examples:
    -- (1, 'QUEEN_STD', 'QUEEN', 1)
    -- (2, 'ROLLAWAY', 'ROLLAWAY', 0)
);

CREATE TABLE room_bed (
    roomId INTEGER NOT NULL,
    bedTypeId INTEGER NOT NULL,
    quantity INTEGER NOT NULL CHECK (quantity >= 1),
    PRIMARY KEY (roomId, bedTypeId),
    FOREIGN KEY (roomId) REFERENCES room(roomId),
    FOREIGN KEY (bedTypeId) REFERENCES bed_type(bedTypeId)
    -- examples:
    -- (205, 1, 2)
    -- (318, 2, 1)
);

CREATE TABLE adjacent (
    roomId1 INTEGER NOT NULL,
    roomId2 INTEGER NOT NULL,
    doorType TEXT NOT NULL CHECK (doorType IN ('PRIVATE_DOOR', 'MOVABLE_WALL_DOOR')),
    PRIMARY KEY (roomId1, roomId2),
    FOREIGN KEY (roomId1) REFERENCES room(roomId),
    FOREIGN KEY (roomId2) REFERENCES room(roomId),
    CHECK (roomId1 <> roomId2)
    -- examples:
    -- (401, 402, 'MOVABLE_WALL_DOOR')
    -- (205, 206, 'PRIVATE_DOOR')
);

-- =====================================================
-- ROOM STATUS
-- "UNDER MAINTENANCE" = RENOVATION / RECONSTRUCTION / OUT_OF_SERVICE
-- =====================================================

CREATE TABLE room_status (
    statusId INTEGER PRIMARY KEY,
    roomId INTEGER NOT NULL,
    statusType TEXT NOT NULL CHECK (
        statusType IN (
            'AVAILABLE',
            'OCCUPIED',
            'DIRTY',
            'READY',
            'RENOVATION',
            'RECONSTRUCTION',
            'OUT_OF_SERVICE'
        )
    ),
    startTime TIMESTAMP NOT NULL,               -- example: '2026-04-16 08:00:00'
    endTime TIMESTAMP,                          -- NULL = still current
    employeeId INTEGER,
    notes TEXT,
    FOREIGN KEY (roomId) REFERENCES room(roomId),
    CHECK (endTime IS NULL OR endTime >= startTime)
    -- examples:
    -- (1, 205, 'DIRTY', '2026-04-16 11:00:00', NULL, 1, 'Awaiting housekeeping')
    -- (2, 401, 'RENOVATION', '2026-04-01 00:00:00', '2026-04-30 23:59:59', 2, 'Projector replacement')
);

-- =====================================================
-- PEOPLE / GUESTS / EMPLOYEES / ORGANIZATIONS / PARTIES
-- =====================================================

CREATE TABLE person (
    personId INTEGER PRIMARY KEY,
    firstName TEXT NOT NULL,
    lastName TEXT NOT NULL,
    emailAddress TEXT,
    phoneNumber TEXT
    -- example: (1, 'Emma', 'Lee', 'emma.lee@email.com', '917-555-0101')
);

CREATE TABLE organization (
    organizationId INTEGER PRIMARY KEY,
    organizationName TEXT NOT NULL UNIQUE
    -- example: (1, 'NYU Shanghai')
);

CREATE TABLE guest (
    guestId INTEGER PRIMARY KEY,
    personId INTEGER NOT NULL UNIQUE,
    pinCode TEXT NOT NULL,
    isConfidential INTEGER NOT NULL DEFAULT 0 CHECK (isConfidential IN (0,1)),
    FOREIGN KEY (personId) REFERENCES person(personId)
    -- example: (1, 1, '4829', 1)
);

CREATE TABLE employee (
    employeeId INTEGER PRIMARY KEY,
    personId INTEGER NOT NULL UNIQUE,
    jobTitle TEXT NOT NULL,
    FOREIGN KEY (personId) REFERENCES person(personId)
    -- example: (1, 2, 'Front Desk Clerk')
);

CREATE TABLE organization_member (
    organizationId INTEGER NOT NULL,
    personId INTEGER NOT NULL,
    PRIMARY KEY (organizationId, personId),
    FOREIGN KEY (organizationId) REFERENCES organization(organizationId),
    FOREIGN KEY (personId) REFERENCES person(personId)
    -- example: (1, 3)
);

CREATE TABLE party (
    partyId INTEGER PRIMARY KEY,
    partyType TEXT NOT NULL CHECK (partyType IN ('PERSON','ORGANIZATION')),
    personId INTEGER,
    organizationId INTEGER,
    authorizedRepPersonId INTEGER,
    FOREIGN KEY (personId) REFERENCES person(personId),
    FOREIGN KEY (organizationId) REFERENCES organization(organizationId),
    FOREIGN KEY (authorizedRepPersonId) REFERENCES person(personId),
    CHECK (
        (partyType = 'PERSON' AND personId IS NOT NULL AND organizationId IS NULL)
        OR
        (partyType = 'ORGANIZATION' AND organizationId IS NOT NULL AND personId IS NULL)
    )
    -- examples:
    -- (1, 'PERSON', 1, NULL, NULL)
    -- (2, 'ORGANIZATION', NULL, 1, 3)
);

-- =====================================================
-- RESERVATIONS / PREFERENCES / ACTUAL STAY ASSIGNMENTS
-- =====================================================

CREATE TABLE reservation (
    reservationId INTEGER PRIMARY KEY,
    bookedByPartyId INTEGER NOT NULL,
    billingPartyId INTEGER NOT NULL,
    bookingDate DATE NOT NULL,
    plannedCheckInDate DATE NOT NULL,
    plannedCheckOutDate DATE NOT NULL,
    reservationStatus TEXT NOT NULL CHECK (
        reservationStatus IN ('BOOKED','CHECKED_IN','CHECKED_OUT','CANCELLED')
    ),
    advanceDeposit DECIMAL(10,2) NOT NULL DEFAULT 0 CHECK (advanceDeposit >= 0),
    FOREIGN KEY (bookedByPartyId) REFERENCES party(partyId),
    FOREIGN KEY (billingPartyId) REFERENCES party(partyId),
    CHECK (plannedCheckOutDate > plannedCheckInDate)
    -- example:
    -- (1, 1, 1, '2026-04-01', '2026-04-15', '2026-04-18', 'BOOKED', 100.00)
);

CREATE TABLE reservation_preference (
    preferenceId INTEGER PRIMARY KEY,
    reservationId INTEGER NOT NULL UNIQUE,
    numGuests INTEGER NOT NULL CHECK (numGuests > 0),
    smokingPref INTEGER CHECK (smokingPref IN (0,1)),
    proximityPref TEXT,                         -- example: 'near parking'
    notes TEXT,
    FOREIGN KEY (reservationId) REFERENCES reservation(reservationId)
    -- example:
    -- (1, 1, 2, 0, 'near parking', 'quiet room if possible')
);

CREATE TABLE reservation_bed_preference (
    preferenceId INTEGER NOT NULL,
    bedTypeId INTEGER NOT NULL,
    preferredQuantity INTEGER NOT NULL CHECK (preferredQuantity > 0),
    PRIMARY KEY (preferenceId, bedTypeId),
    FOREIGN KEY (preferenceId) REFERENCES reservation_preference(preferenceId),
    FOREIGN KEY (bedTypeId) REFERENCES bed_type(bedTypeId)
    -- example:
    -- (1, 1, 2)
);

CREATE TABLE stay_room_assignment (
    stayAssignmentId INTEGER PRIMARY KEY,
    reservationId INTEGER NOT NULL,
    roomId INTEGER NOT NULL,
    assignedStartDate DATE NOT NULL,
    assignedEndDate DATE,                       -- NULL if still occupying / open-ended
    assignmentStatus TEXT NOT NULL CHECK (
        assignmentStatus IN ('RESERVED','OCCUPIED','RELEASED')
    ),
    FOREIGN KEY (reservationId) REFERENCES reservation(reservationId),
    FOREIGN KEY (roomId) REFERENCES room(roomId),
    CHECK (assignedEndDate IS NULL OR assignedEndDate > assignedStartDate)
    -- examples:
    -- (1, 1, 205, '2026-04-15', '2026-04-16', 'RELEASED')
    -- (2, 1, 318, '2026-04-16', NULL, 'OCCUPIED')
);

CREATE TABLE stay_room_guest (
    stayAssignmentId INTEGER NOT NULL,
    guestId INTEGER NOT NULL,
    occupantRole TEXT NOT NULL CHECK (occupantRole IN ('PRIMARY','SHARER')),
    PRIMARY KEY (stayAssignmentId, guestId),
    FOREIGN KEY (stayAssignmentId) REFERENCES stay_room_assignment(stayAssignmentId),
    FOREIGN KEY (guestId) REFERENCES guest(guestId)
    -- examples:
    -- (1, 1, 'PRIMARY')
    -- (2, 4, 'SHARER')
);

CREATE TABLE room_extension (
    extensionId INTEGER PRIMARY KEY,
    stayAssignmentId INTEGER NOT NULL,
    extensionHours INTEGER NOT NULL CHECK (extensionHours > 0),
    surchargeAmount DECIMAL(10,2) NOT NULL DEFAULT 0 CHECK (surchargeAmount >= 0),
    FOREIGN KEY (stayAssignmentId) REFERENCES stay_room_assignment(stayAssignmentId)
    -- example:
    -- (1, 2, 3, 50.00)
);

-- =====================================================
-- EVENTS / GUESTS / ORGANIZATIONS / ROOM USAGE
-- =====================================================

CREATE TABLE event (
    eventId INTEGER PRIMARY KEY,
    eventName TEXT NOT NULL,
    hostGuestId INTEGER,
    billedPartyId INTEGER NOT NULL,
    startDate DATE NOT NULL,
    endDate DATE NOT NULL,
    estimatedAttendance INTEGER CHECK (estimatedAttendance >= 0),
    estimatedGuestCount INTEGER CHECK (estimatedGuestCount >= 0),
    FOREIGN KEY (hostGuestId) REFERENCES guest(guestId),
    FOREIGN KEY (billedPartyId) REFERENCES party(partyId),
    CHECK (endDate >= startDate)
    -- example:
    -- (1, 'Admissions Dinner', 1, 2, '2026-04-16', '2026-04-16', 120, 25)
);

CREATE TABLE event_guest (
    eventId INTEGER NOT NULL,
    guestId INTEGER NOT NULL,
    roleName TEXT,                              -- example: 'HOST', 'ATTENDEE', 'SPEAKER'
    PRIMARY KEY (eventId, guestId),
    FOREIGN KEY (eventId) REFERENCES event(eventId),
    FOREIGN KEY (guestId) REFERENCES guest(guestId)
    -- examples:
    -- (1, 1, 'HOST')
    -- (1, 4, 'ATTENDEE')
);

CREATE TABLE event_organization (
    eventId INTEGER NOT NULL,
    organizationId INTEGER NOT NULL,
    roleName TEXT,                              -- example: 'SPONSOR'
    PRIMARY KEY (eventId, organizationId),
    FOREIGN KEY (eventId) REFERENCES event(eventId),
    FOREIGN KEY (organizationId) REFERENCES organization(organizationId)
    -- example:
    -- (1, 1, 'SPONSOR')
);

CREATE TABLE event_room_usage (
    usageId INTEGER PRIMARY KEY,
    eventId INTEGER NOT NULL,
    roomId INTEGER NOT NULL,
    usageDate DATE NOT NULL,                    -- example: '2026-04-16'
    usageSlot TEXT NOT NULL CHECK (
        usageSlot IN ('BREAKFAST','MORNING','LUNCH','AFTERNOON','SUPPER','EVENING','NIGHT')
    ),
    isEatingUsage INTEGER NOT NULL CHECK (isEatingUsage IN (0,1)),
    FOREIGN KEY (eventId) REFERENCES event(eventId),
    FOREIGN KEY (roomId) REFERENCES room(roomId),
    UNIQUE (roomId, usageDate, usageSlot)
    -- examples:
    -- (1, 1, 401, '2026-04-16', 'LUNCH', 1)
    -- (2, 1, 401, '2026-04-16', 'AFTERNOON', 0)
);

-- =====================================================
-- BILLING / ACCOUNTS / CHARGES / PAYMENTS
-- =====================================================

CREATE TABLE account (
    accountId INTEGER PRIMARY KEY,
    reservationId INTEGER,
    eventId INTEGER,
    accountName TEXT NOT NULL,
    accountStatus TEXT NOT NULL CHECK (accountStatus IN ('OPEN','CLOSED','VOID')),
    openedAt TIMESTAMP NOT NULL,
    closedAt TIMESTAMP,
    FOREIGN KEY (reservationId) REFERENCES reservation(reservationId),
    FOREIGN KEY (eventId) REFERENCES event(eventId),
    CHECK (
        (reservationId IS NOT NULL AND eventId IS NULL)
        OR
        (reservationId IS NULL AND eventId IS NOT NULL)
    ),
    CHECK (closedAt IS NULL OR closedAt >= openedAt)
    -- examples:
    -- (1, 1, NULL, 'Room and tax - Emma', 'OPEN', '2026-04-15 16:00:00', NULL)
    -- (2, NULL, 1, 'Admissions Dinner Master Bill', 'OPEN', '2026-04-01 09:00:00', NULL)
);

CREATE TABLE account_responsibility (
    accountId INTEGER NOT NULL,
    partyId INTEGER NOT NULL,
    responsibilityType TEXT NOT NULL CHECK (
        responsibilityType IN ('FULL','SPLIT','BACKUP')
    ),
    responsibilityPercent DECIMAL(5,2),
    PRIMARY KEY (accountId, partyId),
    FOREIGN KEY (accountId) REFERENCES account(accountId),
    FOREIGN KEY (partyId) REFERENCES party(partyId),
    CHECK (
        responsibilityPercent IS NULL
        OR (responsibilityPercent >= 0 AND responsibilityPercent <= 100)
    )
    -- examples:
    -- (1, 1, 'FULL', 100.00)
    -- (2, 2, 'FULL', 100.00)
    -- (2, 1, 'BACKUP', NULL)
);

CREATE TABLE charge (
    chargeId INTEGER PRIMARY KEY,
    accountId INTEGER NOT NULL,
    chargeType TEXT NOT NULL CHECK (
        chargeType IN (
            'ROOM_RATE',
            'ROOM_SURCHARGE',
            'PHONE',
            'ROOM_SERVICE',
            'BUSINESS_SERVICE',
            'RETAIL',
            'HEALTH_CLUB',
            'MEETING_ROOM',
            'FOOD_BEVERAGE',
            'OTHER'
        )
    ),
    description TEXT,
    amount DECIMAL(10,2) NOT NULL CHECK (amount >= 0),
    chargeTime TIMESTAMP NOT NULL,
    usedByGuestId INTEGER,
    stayAssignmentId INTEGER,
    eventId INTEGER,
    createdByEmployeeId INTEGER,
    FOREIGN KEY (accountId) REFERENCES account(accountId),
    FOREIGN KEY (usedByGuestId) REFERENCES guest(guestId),
    FOREIGN KEY (stayAssignmentId) REFERENCES stay_room_assignment(stayAssignmentId),
    FOREIGN KEY (eventId) REFERENCES event(eventId),
    FOREIGN KEY (createdByEmployeeId) REFERENCES employee(employeeId)
    -- examples:
    -- (1, 1, 'ROOM_RATE', 'Nightly room charge', 220.00, '2026-04-15 16:00:00', NULL, 1, NULL, 1)
    -- (2, 1, 'PHONE', 'International call', 18.00, '2026-04-15 21:30:00', 1, 1, NULL, 1)
    -- (3, 2, 'FOOD_BEVERAGE', 'Event lunch catering', 1800.00, '2026-04-16 12:00:00', NULL, NULL, 1, 1)
);

CREATE TABLE payment (
    paymentId INTEGER PRIMARY KEY,
    accountId INTEGER NOT NULL,
    paidByPartyId INTEGER NOT NULL,
    paymentMethod TEXT NOT NULL,               -- example: 'VISA', 'AMEX', 'CASH'
    amount DECIMAL(10,2) NOT NULL CHECK (amount > 0),
    paymentTime TIMESTAMP NOT NULL,
    referenceNumber TEXT,
    FOREIGN KEY (accountId) REFERENCES account(accountId),
    FOREIGN KEY (paidByPartyId) REFERENCES party(partyId)
    -- example:
    -- (1, 1, 1, 'VISA', 238.00, '2026-04-18 11:50:00', 'AUTH83492')
);

-- =====================================================
-- CONTACT / TRACKING
-- =====================================================

CREATE TABLE card_swipe_log (
    logId INTEGER PRIMARY KEY,
    readerId INTEGER NOT NULL,
    guestId INTEGER,
    employeeId INTEGER,
    direction TEXT NOT NULL CHECK (direction IN ('IN','OUT')),
    swipeTime TIMESTAMP NOT NULL,
    FOREIGN KEY (guestId) REFERENCES guest(guestId),
    FOREIGN KEY (employeeId) REFERENCES employee(employeeId),
    CHECK (
        (guestId IS NOT NULL AND employeeId IS NULL)
        OR
        (guestId IS NULL AND employeeId IS NOT NULL)
    )
    -- examples:
    -- (1, 15, 1, NULL, 'IN', '2026-04-16 11:58:00')
    -- (2, 22, NULL, 1, 'OUT', '2026-04-16 14:10:00')
);

CREATE TABLE guest_message (
    messageId INTEGER PRIMARY KEY,
    guestId INTEGER NOT NULL,
    messageContent TEXT NOT NULL,
    messageTime TIMESTAMP NOT NULL,
    FOREIGN KEY (guestId) REFERENCES guest(guestId)
    -- example:
    -- (1, 1, 'Please call front desk when you return.', '2026-04-16 18:30:00')
);
