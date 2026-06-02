PRAGMA foreign_keys = ON;

CREATE TABLE hotel (
    hotelId INTEGER PRIMARY KEY,
    name TEXT NOT NULL
);

CREATE TABLE building (
    buildingId INTEGER PRIMARY KEY,
    hotelId INTEGER NOT NULL,
    buildingName TEXT NOT NULL,
    FOREIGN KEY (hotelId) REFERENCES hotel(hotelId),
    UNIQUE (hotelId, buildingName)
);

CREATE TABLE wing (
    wingId INTEGER PRIMARY KEY,
    buildingId INTEGER NOT NULL,
    wingCode TEXT NOT NULL,
    wingOrder INTEGER NOT NULL,
    nearIndoorPool INTEGER NOT NULL DEFAULT 0 CHECK (nearIndoorPool IN (0, 1)),
    nearOutdoorPool INTEGER NOT NULL DEFAULT 0 CHECK (nearOutdoorPool IN (0, 1)),
    nearParking INTEGER NOT NULL DEFAULT 0 CHECK (nearParking IN (0, 1)),
    handicapAccess INTEGER NOT NULL DEFAULT 0 CHECK (handicapAccess IN (0, 1)),
    FOREIGN KEY (buildingId) REFERENCES building(buildingId),
    UNIQUE (buildingId, wingCode),
    UNIQUE (buildingId, wingOrder)
);

CREATE TABLE level (
    levelId INTEGER PRIMARY KEY,
    wingId INTEGER NOT NULL,
    levelNumber INTEGER NOT NULL,
    isSmoking INTEGER NOT NULL CHECK (isSmoking IN (0, 1)),
    FOREIGN KEY (wingId) REFERENCES wing(wingId),
    UNIQUE (wingId, levelNumber)
);

CREATE TABLE room (
    roomId INTEGER PRIMARY KEY,
    levelId INTEGER NOT NULL,
    roomNum TEXT NOT NULL,
    isSmokingOverride INTEGER DEFAULT NULL CHECK (isSmokingOverride IN (0, 1)),
    FOREIGN KEY (levelId) REFERENCES level(levelId),
    UNIQUE (levelId, roomNum)
);

CREATE TABLE capability_type (
    capabilityTypeId INTEGER PRIMARY KEY,
    capabilityCode TEXT NOT NULL UNIQUE
);

CREATE TABLE room_capability (
    roomId INTEGER NOT NULL,
    capabilityTypeId INTEGER NOT NULL,
    capacity INTEGER NOT NULL CHECK (capacity > 0),
    baseRate DECIMAL(10, 2) NOT NULL CHECK (baseRate >= 0),
    isAssignable INTEGER NOT NULL DEFAULT 1 CHECK (isAssignable IN (0, 1)),
    PRIMARY KEY (roomId, capabilityTypeId),
    FOREIGN KEY (roomId) REFERENCES room(roomId),
    FOREIGN KEY (capabilityTypeId) REFERENCES capability_type(capabilityTypeId)
);

CREATE TABLE fixture_type (
    fixtureTypeId INTEGER PRIMARY KEY,
    fixtureCode TEXT NOT NULL UNIQUE
);

CREATE TABLE room_fixture (
    roomId INTEGER NOT NULL,
    fixtureTypeId INTEGER NOT NULL,
    PRIMARY KEY (roomId, fixtureTypeId),
    FOREIGN KEY (roomId) REFERENCES room(roomId),
    FOREIGN KEY (fixtureTypeId) REFERENCES fixture_type(fixtureTypeId)
);

CREATE TABLE bed_type (
    bedTypeId INTEGER PRIMARY KEY,
    bedCode TEXT NOT NULL UNIQUE,
    size TEXT NOT NULL,
    isPermanent INTEGER NOT NULL CHECK (isPermanent IN (0, 1))
);

CREATE TABLE room_bed (
    roomId INTEGER NOT NULL,
    bedTypeId INTEGER NOT NULL,
    quantity INTEGER NOT NULL CHECK (quantity >= 1),
    PRIMARY KEY (roomId, bedTypeId),
    FOREIGN KEY (roomId) REFERENCES room(roomId),
    FOREIGN KEY (bedTypeId) REFERENCES bed_type(bedTypeId)
);

CREATE TABLE adjacent (
    roomId1 INTEGER NOT NULL,
    roomId2 INTEGER NOT NULL,
    doorType TEXT NOT NULL CHECK (doorType IN ('PRIVATE_DOOR', 'MOVABLE_WALL_DOOR')),
    PRIMARY KEY (roomId1, roomId2),
    FOREIGN KEY (roomId1) REFERENCES room(roomId),
    FOREIGN KEY (roomId2) REFERENCES room(roomId),
    CHECK (roomId1 <> roomId2)
);

CREATE TABLE room_status (
    statusId INTEGER PRIMARY KEY,
    roomId INTEGER NOT NULL,
        statusType TEXT NOT NULL CHECK (
            statusType IN (
            'OCCUPIED',
            'DIRTY',
            'READY',
            'RENOVATION',
            'RECONSTRUCTION',
            'OUT_OF_SERVICE'
        )
    ),
    startTime DATE NOT NULL,
    endTime DATE NOT NULL,
    employeeId INTEGER,
    notes TEXT,
    FOREIGN KEY (roomId) REFERENCES room(roomId),
    CHECK (endTime >= startTime)
);

CREATE TABLE person (
    personId INTEGER PRIMARY KEY,
    firstName TEXT NOT NULL,
    lastName TEXT NOT NULL,
    emailAddress TEXT,
    phoneNumber TEXT
);

CREATE TABLE organization (
    organizationId INTEGER PRIMARY KEY,
    organizationName TEXT NOT NULL UNIQUE
);

CREATE TABLE guest (
    guestId INTEGER PRIMARY KEY,
    personId INTEGER NOT NULL UNIQUE,
    pinCode TEXT NOT NULL,
    isConfidential INTEGER NOT NULL DEFAULT 0 CHECK (isConfidential IN (0, 1)),
    FOREIGN KEY (personId) REFERENCES person(personId)
);

CREATE TABLE employee (
    employeeId INTEGER PRIMARY KEY,
    personId INTEGER NOT NULL UNIQUE,
    jobTitle TEXT NOT NULL,
    FOREIGN KEY (personId) REFERENCES person(personId)
);

CREATE TABLE organization_member (
    organizationId INTEGER NOT NULL,
    personId INTEGER NOT NULL,
    PRIMARY KEY (organizationId, personId),
    FOREIGN KEY (organizationId) REFERENCES organization(organizationId),
    FOREIGN KEY (personId) REFERENCES person(personId)
);

CREATE TABLE party (
    partyId INTEGER PRIMARY KEY,
    partyType TEXT NOT NULL CHECK (partyType IN ('PERSON', 'ORGANIZATION')),
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
);

CREATE TABLE reservation (
    reservationId INTEGER PRIMARY KEY,
    bookedByPartyId INTEGER NOT NULL,
    billingPartyId INTEGER NOT NULL,
    bookingDate DATE NOT NULL,
    plannedCheckInDate DATE NOT NULL,
    plannedCheckOutDate DATE NOT NULL,
    reservationStatus TEXT NOT NULL CHECK (
        reservationStatus IN ('BOOKED', 'CHECKED_IN', 'CHECKED_OUT', 'CANCELLED')
    ),
    advanceDeposit DECIMAL(10, 2) NOT NULL DEFAULT 0 CHECK (advanceDeposit >= 0),
    FOREIGN KEY (bookedByPartyId) REFERENCES party(partyId),
    FOREIGN KEY (billingPartyId) REFERENCES party(partyId),
    CHECK (plannedCheckOutDate > plannedCheckInDate)
);

CREATE TABLE reservation_preference (
    preferenceId INTEGER PRIMARY KEY,
    reservationId INTEGER NOT NULL UNIQUE,
    numGuests INTEGER NOT NULL CHECK (numGuests > 0),
    smokingPref INTEGER CHECK (smokingPref IN (0, 1)),
    proximityPref TEXT,
    notes TEXT,
    FOREIGN KEY (reservationId) REFERENCES reservation(reservationId)
);

CREATE TABLE reservation_bed_preference (
    preferenceId INTEGER NOT NULL,
    bedTypeId INTEGER NOT NULL,
    preferredQuantity INTEGER NOT NULL CHECK (preferredQuantity > 0),
    PRIMARY KEY (preferenceId, bedTypeId),
    FOREIGN KEY (preferenceId) REFERENCES reservation_preference(preferenceId),
    FOREIGN KEY (bedTypeId) REFERENCES bed_type(bedTypeId)
);

CREATE TABLE stay_room_assignment (
    stayAssignmentId INTEGER PRIMARY KEY,
    reservationId INTEGER NOT NULL,
    roomId INTEGER NOT NULL,
    assignedStartDate DATE NOT NULL,
    assignedEndDate DATE,
    assignmentStatus TEXT NOT NULL CHECK (
        assignmentStatus IN ('RESERVED', 'OCCUPIED', 'RELEASED')
    ),
    FOREIGN KEY (reservationId) REFERENCES reservation(reservationId),
    FOREIGN KEY (roomId) REFERENCES room(roomId),
    CHECK (assignedEndDate IS NULL OR assignedEndDate > assignedStartDate)
);

CREATE TABLE stay_room_guest (
    stayAssignmentId INTEGER NOT NULL,
    guestId INTEGER NOT NULL,
    occupantRole TEXT NOT NULL CHECK (occupantRole IN ('PRIMARY', 'SHARER')),
    PRIMARY KEY (stayAssignmentId, guestId),
    FOREIGN KEY (stayAssignmentId) REFERENCES stay_room_assignment(stayAssignmentId),
    FOREIGN KEY (guestId) REFERENCES guest(guestId)
);

CREATE TABLE room_extension (
    extensionId INTEGER PRIMARY KEY,
    stayAssignmentId INTEGER NOT NULL,
    extensionHours INTEGER NOT NULL CHECK (extensionHours > 0),
    surchargeAmount DECIMAL(10, 2) NOT NULL DEFAULT 0 CHECK (surchargeAmount >= 0),
    FOREIGN KEY (stayAssignmentId) REFERENCES stay_room_assignment(stayAssignmentId)
);

CREATE TABLE event (
    eventId INTEGER PRIMARY KEY,
    eventName TEXT NOT NULL,
    hostPartyId INTEGER,
    billedPartyId INTEGER NOT NULL,
    startDate DATE NOT NULL,
    endDate DATE NOT NULL,
    estimatedAttendance INTEGER CHECK (estimatedAttendance >= 0),
    estimatedGuestCount INTEGER CHECK (estimatedGuestCount >= 0),
    FOREIGN KEY (hostPartyId) REFERENCES party(partyId),
    FOREIGN KEY (billedPartyId) REFERENCES party(partyId),
    CHECK (endDate >= startDate)
);

CREATE TABLE event_guest (
    eventId INTEGER NOT NULL,
    guestId INTEGER NOT NULL,
    roleName TEXT,
    PRIMARY KEY (eventId, guestId),
    FOREIGN KEY (eventId) REFERENCES event(eventId),
    FOREIGN KEY (guestId) REFERENCES guest(guestId)
);

CREATE TABLE event_organization (
    eventId INTEGER NOT NULL,
    organizationId INTEGER NOT NULL,
    roleName TEXT,
    PRIMARY KEY (eventId, organizationId),
    FOREIGN KEY (eventId) REFERENCES event(eventId),
    FOREIGN KEY (organizationId) REFERENCES organization(organizationId)
);

CREATE TABLE event_room_usage (
    usageId INTEGER PRIMARY KEY,
    eventId INTEGER NOT NULL,
    roomId INTEGER NOT NULL,
    usageDate DATE NOT NULL,
    usageSlot TEXT NOT NULL CHECK (
        usageSlot IN ('BREAKFAST', 'MORNING', 'LUNCH', 'AFTERNOON', 'SUPPER', 'EVENING', 'NIGHT')
    ),
    isEatingUsage INTEGER NOT NULL CHECK (isEatingUsage IN (0, 1)),
    FOREIGN KEY (eventId) REFERENCES event(eventId),
    FOREIGN KEY (roomId) REFERENCES room(roomId),
    UNIQUE (roomId, usageDate, usageSlot)
);

CREATE TABLE account (
    accountId INTEGER PRIMARY KEY,
    reservationId INTEGER,
    eventId INTEGER,
    accountName TEXT NOT NULL,
    accountStatus TEXT NOT NULL CHECK (accountStatus IN ('OPEN', 'CLOSED', 'VOID')),
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
);

CREATE TABLE account_responsibility (
    accountId INTEGER NOT NULL,
    partyId INTEGER NOT NULL,
    responsibilityType TEXT NOT NULL CHECK (
        responsibilityType IN ('FULL', 'SPLIT', 'BACKUP')
    ),
    responsibilityPercent DECIMAL(5, 2),
    PRIMARY KEY (accountId, partyId),
    FOREIGN KEY (accountId) REFERENCES account(accountId),
    FOREIGN KEY (partyId) REFERENCES party(partyId),
    CHECK (
        responsibilityPercent IS NULL
        OR (responsibilityPercent >= 0 AND responsibilityPercent <= 100)
    )
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
    amount DECIMAL(10, 2) NOT NULL CHECK (amount >= 0),
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
);

CREATE TABLE payment (
    paymentId INTEGER PRIMARY KEY,
    accountId INTEGER NOT NULL,
    paidByPartyId INTEGER NOT NULL,
    paymentMethod TEXT NOT NULL,
    amount DECIMAL(10, 2) NOT NULL CHECK (amount > 0),
    paymentTime TIMESTAMP NOT NULL,
    referenceNumber TEXT,
    FOREIGN KEY (accountId) REFERENCES account(accountId),
    FOREIGN KEY (paidByPartyId) REFERENCES party(partyId)
);

CREATE TABLE reader (
    readerId INTEGER PRIMARY KEY,
    readerName TEXT NOT NULL UNIQUE,
    readerType TEXT NOT NULL CHECK (readerType IN ('ROOM', 'MEETING_ROOM', 'FACILITY', 'ENTRY')),
    roomId INTEGER,
    locationDescription TEXT NOT NULL,
    FOREIGN KEY (roomId) REFERENCES room(roomId)
);

CREATE TABLE card_swipe_log (
    logId INTEGER PRIMARY KEY,
    readerId INTEGER NOT NULL,
    guestId INTEGER,
    employeeId INTEGER,
    direction TEXT NOT NULL CHECK (direction IN ('IN', 'OUT')),
    swipeTime TIMESTAMP NOT NULL,
    FOREIGN KEY (readerId) REFERENCES reader(readerId),
    FOREIGN KEY (guestId) REFERENCES guest(guestId),
    FOREIGN KEY (employeeId) REFERENCES employee(employeeId),
    CHECK (
        (guestId IS NOT NULL AND employeeId IS NULL)
        OR
        (guestId IS NULL AND employeeId IS NOT NULL)
    )
);

CREATE TABLE guest_message (
    messageId INTEGER PRIMARY KEY,
    guestId INTEGER NOT NULL,
    messageContent TEXT NOT NULL,
    messageTime TIMESTAMP NOT NULL,
    FOREIGN KEY (guestId) REFERENCES guest(guestId)
);
