PRAGMA foreign_keys = ON;

-- =====================================================
-- BASIC HOTEL STRUCTURE
-- =====================================================

INSERT INTO hotel (hotelId, name) VALUES
(1, 'Last Resort Hotel');

INSERT INTO building (buildingId, hotelId, buildingName) VALUES
(1, 1, 'Main Building');

INSERT INTO wing (wingId, buildingId, wingCode, wingOrder, nearIndoorPool, nearOutdoorPool, nearParking, handicapAccess) VALUES
(1, 1, 'A', 1, 1, 0, 1, 1),
(2, 1, 'B', 2, 0, 1, 0, 1);

INSERT INTO level (levelId, wingId, levelNumber, isSmoking) VALUES
(1, 1, 1, 0),
(2, 1, 2, 0),
(3, 2, 1, 1),
(4, 2, 2, 0);

-- =====================================================
-- ROOMS (20 ROOMS)
-- =====================================================

INSERT INTO room (roomId, levelId, roomNum, isSmokingOverride) VALUES
(1, 1, '101', NULL),
(2, 1, '102', NULL),
(3, 1, '103', NULL),
(4, 1, '104', NULL),
(5, 1, '105', NULL),

(6, 2, '201', NULL),
(7, 2, '202', NULL),
(8, 2, '203', NULL),
(9, 2, '204', NULL),
(10, 2, '205', NULL),

(11, 3, 'B101', 1),
(12, 3, 'B102', 1),
(13, 3, 'B103', 1),
(14, 3, 'B104', 1),
(15, 3, 'B105', 1),

(16, 4, 'B201', NULL),
(17, 4, 'B202', NULL),
(18, 4, 'B203', NULL),
(19, 4, 'B204', NULL),
(20, 4, 'B205', NULL);

-- =====================================================
-- TYPES / FIXTURES / BEDS
-- =====================================================

INSERT INTO capability_type (capabilityTypeId, capabilityCode) VALUES
(1, 'SLEEPING'),
(2, 'MEETING'),
(3, 'SUITE');

INSERT INTO fixture_type (fixtureTypeId, fixtureCode) VALUES
(1, 'TOILET_BATH'),
(2, 'EXTRA_MEETING_SPACE'),
(3, 'OUTDOOR_SPACE');

INSERT INTO bed_type (bedTypeId, bedCode, size, isPermanent) VALUES
(1, 'QUEEN_STD', 'QUEEN', 1),
(2, 'KING_STD', 'KING', 1),
(3, 'TWIN_STD', 'TWIN', 1),
(4, 'ROLLAWAY', 'ROLLAWAY', 0);

-- =====================================================
-- ROOM CAPABILITIES
-- Rules enforced:
-- - sleeping rooms have toilet/bath
-- - suites have toilet/bath + extra meeting space
-- - meeting-only rooms have no permanent beds
-- =====================================================

-- Sleeping rooms
INSERT INTO room_capability (roomId, capabilityTypeId, capacity, baseRate, isAssignable) VALUES
(1, 1, 2, 180.00, 1),
(2, 1, 2, 180.00, 1),
(3, 1, 3, 210.00, 1),
(4, 1, 2, 185.00, 1),
(5, 1, 1, 150.00, 1),
(6, 1, 2, 195.00, 1),
(7, 1, 2, 195.00, 1),
(8, 1, 4, 240.00, 1),
(11, 1, 2, 170.00, 1),
(12, 1, 2, 170.00, 1),
(13, 1, 2, 175.00, 1),
(16, 1, 2, 200.00, 1),
(17, 1, 2, 200.00, 1),
(20, 1, 1, 145.00, 1);

-- Suites
INSERT INTO room_capability (roomId, capabilityTypeId, capacity, baseRate, isAssignable) VALUES
(9, 3, 4, 320.00, 1),
(10, 3, 5, 380.00, 1),
(18, 3, 4, 330.00, 1);

-- Meeting rooms
INSERT INTO room_capability (roomId, capabilityTypeId, capacity, baseRate, isAssignable) VALUES
(14, 2, 20, 250.00, 1),
(15, 2, 60, 600.00, 1),
(19, 2, 12, 180.00, 1);

-- Suites can also be meeting-capable
INSERT INTO room_capability (roomId, capabilityTypeId, capacity, baseRate, isAssignable) VALUES
(9, 2, 8, 120.00, 1),
(10, 2, 10, 140.00, 1),
(18, 2, 8, 120.00, 1);

-- =====================================================
-- FIXTURES
-- =====================================================

-- Toilet/bath => all sleeping + suite rooms
INSERT INTO room_fixture (roomId, fixtureTypeId) VALUES
(1, 1),(2, 1),(3, 1),(4, 1),(5, 1),
(6, 1),(7, 1),(8, 1),(9, 1),(10, 1),
(11, 1),(12, 1),(13, 1),(16, 1),(17, 1),
(18, 1),(20, 1);

-- Extra meeting space => suites
INSERT INTO room_fixture (roomId, fixtureTypeId) VALUES
(9, 2),(10, 2),(18, 2);

-- Some outdoor space
INSERT INTO room_fixture (roomId, fixtureTypeId) VALUES
(10, 3),(18, 3);

-- =====================================================
-- BEDS
-- meeting-only rooms 14,15,19 have NO permanent beds
-- suites may have permanent beds; that is okay
-- =====================================================

INSERT INTO room_bed (roomId, bedTypeId, quantity) VALUES
(1, 1, 1),
(2, 1, 1),
(3, 3, 2),
(4, 2, 1),
(5, 3, 1),
(6, 1, 1),
(7, 2, 1),
(8, 1, 2),
(9, 2, 1),
(10, 2, 1),
(10, 4, 1),
(11, 1, 1),
(12, 3, 2),
(13, 2, 1),
(16, 1, 1),
(17, 2, 1),
(18, 2, 1),
(20, 3, 1);

-- =====================================================
-- ADJACENCY
-- =====================================================

INSERT INTO adjacent (roomId1, roomId2, doorType) VALUES
(1, 2, 'PRIVATE_DOOR'),
(3, 4, 'PRIVATE_DOOR'),
(9, 10, 'MOVABLE_WALL_DOOR'),
(14, 15, 'MOVABLE_WALL_DOOR'),
(16, 17, 'PRIVATE_DOOR');

-- =====================================================
-- PEOPLE (10 PEOPLE)
-- =====================================================

INSERT INTO person (personId, firstName, lastName, emailAddress, phoneNumber) VALUES
(1, 'Emma', 'Lee', 'emma.lee@email.com', '917-555-0101'),
(2, 'Noah', 'Kim', 'noah.kim@email.com', '917-555-0102'),
(3, 'Olivia', 'Patel', 'olivia.patel@email.com', '917-555-0103'),
(4, 'Liam', 'Garcia', 'liam.garcia@email.com', '917-555-0104'),
(5, 'Ava', 'Chen', 'ava.chen@email.com', '917-555-0105'),
(6, 'Ethan', 'Wong', 'ethan.wong@email.com', '917-555-0106'),
(7, 'Mia', 'Brown', 'mia.brown@email.com', '917-555-0107'),
(8, 'Lucas', 'Smith', 'lucas.smith@email.com', '917-555-0108'),
(9, 'Sophia', 'Davis', 'sophia.davis@email.com', '917-555-0109'),
(10, 'James', 'Wilson', 'james.wilson@email.com', '917-555-0110');

INSERT INTO organization (organizationId, organizationName) VALUES
(1, 'NYU Shanghai'),
(2, 'BluePeak Consulting'),
(3, 'Sunrise Health Group');

INSERT INTO guest (guestId, personId, pinCode, isConfidential) VALUES
(1, 1, '4829', 0),
(2, 2, '1357', 0),
(3, 3, '7712', 0),
(4, 4, '8841', 0),
(5, 5, '6620', 1),
(6, 6, '9021', 0);

INSERT INTO employee (employeeId, personId, jobTitle) VALUES
(1, 7, 'Front Desk Clerk'),
(2, 8, 'Maintenance Supervisor'),
(3, 9, 'Sales Manager'),
(4, 10, 'Housekeeping Lead');

INSERT INTO organization_member (organizationId, personId) VALUES
(1, 3),
(2, 4),
(3, 5);

-- =====================================================
-- PARTIES
-- =====================================================

INSERT INTO party (partyId, partyType, personId, organizationId, authorizedRepPersonId) VALUES
(1, 'PERSON', 1, NULL, NULL),
(2, 'PERSON', 2, NULL, NULL),
(3, 'PERSON', 3, NULL, NULL),
(4, 'PERSON', 4, NULL, NULL),
(5, 'PERSON', 5, NULL, NULL),
(6, 'PERSON', 6, NULL, NULL),
(7, 'ORGANIZATION', NULL, 1, 3),
(8, 'ORGANIZATION', NULL, 2, 4),
(9, 'ORGANIZATION', NULL, 3, 5);

-- =====================================================
-- RESERVATIONS
-- =====================================================

INSERT INTO reservation (
    reservationId, bookedByPartyId, billingPartyId, bookingDate,
    plannedCheckInDate, plannedCheckOutDate, reservationStatus, advanceDeposit
) VALUES
(1, 1, 1, '2026-03-20', '2026-04-01', '2026-04-04', 'CHECKED_IN', 100.00),
(2, 2, 2, '2026-03-25', '2026-04-01', '2026-04-03', 'CHECKED_IN', 80.00),
(3, 3, 7, '2026-03-18', '2026-04-02', '2026-04-05', 'BOOKED', 150.00),
(4, 4, 8, '2026-03-28', '2026-04-03', '2026-04-06', 'BOOKED', 120.00),
(5, 5, 5, '2026-03-22', '2026-03-31', '2026-04-02', 'CHECKED_IN', 200.00),
(6, 6, 9, '2026-03-27', '2026-04-05', '2026-04-07', 'BOOKED', 90.00);

INSERT INTO reservation_preference (preferenceId, reservationId, numGuests, smokingPref, proximityPref, notes) VALUES
(1, 1, 2, 0, 'near parking', 'quiet room if possible'),
(2, 2, 1, 0, 'near indoor pool', NULL),
(3, 3, 2, 0, 'high floor', 'queen bed preferred'),
(4, 4, 1, 1, 'near outdoor pool', NULL),
(5, 5, 2, 0, 'suite if available', 'late check-out requested'),
(6, 6, 1, 0, 'quiet room', NULL);

INSERT INTO reservation_bed_preference (preferenceId, bedTypeId, preferredQuantity) VALUES
(1, 1, 1),
(2, 2, 1),
(3, 1, 1),
(4, 3, 1),
(5, 2, 1),
(6, 1, 1);

-- =====================================================
-- STAY ROOM ASSIGNMENTS
-- no conflicts with event-room usage below
-- current date assumption around 2026-04-01 / 2026-04-02
-- =====================================================

INSERT INTO stay_room_assignment (
    stayAssignmentId, reservationId, roomId, assignedStartDate, assignedEndDate, assignmentStatus
) VALUES
(1, 1, 1, '2026-04-01', '2026-04-04', 'OCCUPIED'),
(2, 2, 6, '2026-04-01', '2026-04-03', 'OCCUPIED'),
(3, 3, 7, '2026-04-02', '2026-04-05', 'RESERVED'),
(4, 4, 11, '2026-04-03', '2026-04-06', 'RESERVED'),
(5, 5, 10, '2026-03-31', '2026-04-02', 'OCCUPIED'),
(6, 6, 16, '2026-04-05', '2026-04-07', 'RESERVED');

INSERT INTO stay_room_guest (stayAssignmentId, guestId, occupantRole) VALUES
(1, 1, 'PRIMARY'),
(1, 4, 'SHARER'),
(2, 2, 'PRIMARY'),
(3, 3, 'PRIMARY'),
(3, 6, 'SHARER'),
(4, 4, 'PRIMARY'),
(5, 5, 'PRIMARY'),
(5, 6, 'SHARER'),
(6, 6, 'PRIMARY');

INSERT INTO room_extension (extensionId, stayAssignmentId, extensionHours, surchargeAmount) VALUES
(1, 5, 3, 60.00);

-- =====================================================
-- ROOM STATUS
-- Some rooms free, some dirty, some maintenance, some ready
-- Avoid conflicting maintenance on occupied/reserved rooms
-- =====================================================

INSERT INTO room_status (statusId, roomId, statusType, startTime, endTime, employeeId, notes) VALUES
(1, 1, 'OCCUPIED', '2026-04-01 15:00:00', NULL, 1, 'Checked in'),
(2, 6, 'OCCUPIED', '2026-04-01 16:00:00', NULL, 1, 'Checked in'),
(3, 10, 'OCCUPIED', '2026-03-31 15:30:00', NULL, 1, 'Suite occupied'),

(4, 2, 'READY', '2026-04-01 10:00:00', NULL, 4, 'Vacant clean room'),
(5, 3, 'READY', '2026-04-01 10:00:00', NULL, 4, 'Vacant clean room'),
(6, 4, 'DIRTY', '2026-04-01 11:00:00', NULL, 4, 'Awaiting cleaning'),
(7, 5, 'READY', '2026-04-01 09:00:00', NULL, 4, 'Vacant clean room'),
(8, 7, 'READY', '2026-04-01 09:00:00', NULL, 4, 'Reserved for tomorrow'),
(9, 8, 'READY', '2026-04-01 09:00:00', NULL, 4, 'Vacant family room'),
(10, 9, 'READY', '2026-04-01 09:00:00', NULL, 4, 'Suite open'),

(11, 11, 'READY', '2026-04-01 09:00:00', NULL, 4, 'Reserved for upcoming arrival'),
(12, 12, 'OUT_OF_SERVICE', '2026-03-29 08:00:00', '2026-04-04 18:00:00', 2, 'Plumbing issue'),
(13, 13, 'READY', '2026-04-01 09:00:00', NULL, 4, 'Vacant'),
(14, 14, 'READY', '2026-04-01 07:00:00', NULL, 4, 'Meeting room available'),
(15, 15, 'READY', '2026-04-01 07:00:00', NULL, 4, 'Ballroom available'),

(16, 16, 'READY', '2026-04-01 09:00:00', NULL, 4, 'Reserved for future arrival'),
(17, 17, 'RENOVATION', '2026-03-20 08:00:00', '2026-04-10 18:00:00', 2, 'Bathroom remodel'),
(18, 18, 'READY', '2026-04-01 09:00:00', NULL, 4, 'Suite open'),
(19, 19, 'READY', '2026-04-01 07:00:00', NULL, 4, 'Small meeting room open'),
(20, 20, 'READY', '2026-04-01 09:00:00', NULL, 4, 'Vacant single room');

-- =====================================================
-- EVENTS
-- different sizes
-- =====================================================

INSERT INTO event (
    eventId, eventName, hostGuestId, billedPartyId,
    startDate, endDate, estimatedAttendance, estimatedGuestCount
) VALUES
(1, 'Board Lunch', 1, 7, '2026-04-01', '2026-04-01', 12, 4),
(2, 'Consulting Workshop', 4, 8, '2026-04-02', '2026-04-02', 35, 2),
(3, 'Health Networking Mixer', 5, 9, '2026-04-03', '2026-04-03', 70, 3);

INSERT INTO event_guest (eventId, guestId, roleName) VALUES
(1, 1, 'HOST'),
(1, 2, 'ATTENDEE'),
(1, 4, 'ATTENDEE'),
(1, 5, 'ATTENDEE'),

(2, 4, 'HOST'),
(2, 3, 'ATTENDEE'),

(3, 5, 'HOST'),
(3, 6, 'ATTENDEE'),
(3, 1, 'ATTENDEE');

INSERT INTO event_organization (eventId, organizationId, roleName) VALUES
(1, 1, 'SPONSOR'),
(2, 2, 'SPONSOR'),
(3, 3, 'SPONSOR');

-- =====================================================
-- EVENT ROOM USAGE
-- no overlap with occupied/reserved sleeping room assignments
-- uses only meeting rooms / suites not assigned during those dates
-- =====================================================

INSERT INTO event_room_usage (usageId, eventId, roomId, usageDate, usageSlot, isEatingUsage) VALUES
(1, 1, 19, '2026-04-01', 'LUNCH', 1),      -- small lunch in small meeting room
(2, 2, 14, '2026-04-02', 'MORNING', 0),    -- workshop session
(3, 2, 14, '2026-04-02', 'AFTERNOON', 0),  -- workshop continuation
(4, 3, 15, '2026-04-03', 'EVENING', 1),    -- large mixer in ballroom
(5, 3, 18, '2026-04-03', 'AFTERNOON', 0);  -- prep / VIP suite breakout

-- =====================================================
-- ACCOUNTS
-- =====================================================

INSERT INTO account (
    accountId, reservationId, eventId, accountName, accountStatus, openedAt, closedAt
) VALUES
(1, 1, NULL, 'Emma Lee Stay', 'OPEN', '2026-04-01 15:00:00', NULL),
(2, 2, NULL, 'Noah Kim Stay', 'OPEN', '2026-04-01 16:00:00', NULL),
(3, 5, NULL, 'Ava Chen Stay', 'OPEN', '2026-03-31 15:30:00', NULL),

(4, NULL, 1, 'Board Lunch Master Bill', 'OPEN', '2026-03-28 10:00:00', NULL),
(5, NULL, 2, 'Consulting Workshop Master Bill', 'OPEN', '2026-03-29 11:00:00', NULL),
(6, NULL, 3, 'Health Networking Mixer Master Bill', 'OPEN', '2026-03-30 12:00:00', NULL);

INSERT INTO account_responsibility (accountId, partyId, responsibilityType, responsibilityPercent) VALUES
(1, 1, 'FULL', 100.00),
(2, 2, 'FULL', 100.00),
(3, 5, 'FULL', 100.00),
(4, 7, 'FULL', 100.00),
(5, 8, 'FULL', 100.00),
(6, 9, 'FULL', 100.00);

-- =====================================================
-- CHARGES
-- includes room extension as ROOM_SURCHARGE
-- =====================================================

INSERT INTO charge (
    chargeId, accountId, chargeType, description, amount, chargeTime,
    usedByGuestId, stayAssignmentId, eventId, createdByEmployeeId
) VALUES
(1, 1, 'ROOM_RATE', 'Night 1 room charge', 180.00, '2026-04-01 18:00:00', NULL, 1, NULL, 1),
(2, 1, 'ROOM_SERVICE', 'Dinner order', 42.00, '2026-04-01 20:15:00', 1, 1, NULL, 1),
(3, 1, 'PHONE', 'International call', 15.00, '2026-04-01 21:10:00', 1, 1, NULL, 1),

(4, 2, 'ROOM_RATE', 'Night 1 room charge', 195.00, '2026-04-01 18:30:00', NULL, 2, NULL, 1),
(5, 2, 'HEALTH_CLUB', 'Gym day pass', 20.00, '2026-04-01 19:00:00', 2, 2, NULL, 1),

(6, 3, 'ROOM_RATE', 'Suite nightly rate', 380.00, '2026-03-31 18:00:00', NULL, 5, NULL, 1),
(7, 3, 'ROOM_SURCHARGE', 'Late checkout extension - 3 hours', 60.00, '2026-04-01 11:00:00', NULL, 5, NULL, 1),
(8, 3, 'ROOM_SERVICE', 'Breakfast service', 35.00, '2026-04-01 08:30:00', 5, 5, NULL, 1),

(9, 4, 'FOOD_BEVERAGE', 'Catered lunch', 240.00, '2026-04-01 12:00:00', NULL, NULL, 1, 3),
(10, 4, 'MEETING_ROOM', 'Meeting room rental', 180.00, '2026-04-01 12:00:00', NULL, NULL, 1, 3),

(11, 5, 'MEETING_ROOM', 'Workshop room rental', 500.00, '2026-04-02 09:00:00', NULL, NULL, 2, 3),
(12, 5, 'BUSINESS_SERVICE', 'Projector and print package', 85.00, '2026-04-02 09:15:00', NULL, NULL, 2, 3),

(13, 6, 'MEETING_ROOM', 'Ballroom rental', 900.00, '2026-04-03 17:00:00', NULL, NULL, 3, 3),
(14, 6, 'FOOD_BEVERAGE', 'Mixer catering', 1200.00, '2026-04-03 18:00:00', NULL, NULL, 3, 3);

-- =====================================================
-- PAYMENTS
-- =====================================================

INSERT INTO payment (
    paymentId, accountId, paidByPartyId, paymentMethod, amount, paymentTime, referenceNumber
) VALUES
(1, 1, 1, 'VISA', 100.00, '2026-04-01 15:05:00', 'AUTH1001'),
(2, 2, 2, 'MASTERCARD', 80.00, '2026-04-01 16:05:00', 'AUTH1002'),
(3, 3, 5, 'AMEX', 200.00, '2026-03-31 15:35:00', 'AUTH1003'),
(4, 4, 7, 'BANK_TRANSFER', 200.00, '2026-03-30 10:00:00', 'BT2001'),
(5, 5, 8, 'BANK_TRANSFER', 300.00, '2026-03-31 11:00:00', 'BT2002');

-- =====================================================
-- CARD SWIPES / MESSAGES
-- =====================================================

INSERT INTO card_swipe_log (logId, readerId, guestId, employeeId, direction, swipeTime) VALUES
(1, 15, 1, NULL, 'IN', '2026-04-01 15:02:00'),
(2, 15, 2, NULL, 'IN', '2026-04-01 16:01:00'),
(3, 21, NULL, 1, 'IN', '2026-04-01 14:45:00'),
(4, 21, NULL, 4, 'IN', '2026-04-01 08:00:00'),
(5, 15, 5, NULL, 'OUT', '2026-04-01 11:30:00');

INSERT INTO guest_message (messageId, guestId, messageContent, messageTime) VALUES
(1, 1, 'Package waiting at front desk.', '2026-04-01 17:30:00'),
(2, 5, 'Late check-out approved until 2 PM.', '2026-04-01 09:00:00');
