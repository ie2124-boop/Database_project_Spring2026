-- 1. How many reservations and planned room-nights are currently in each reservation status?
SELECT
    r.reservationStatus,
    COUNT(*) AS reservation_count,
    SUM(julianday(r.plannedCheckOutDate) - julianday(r.plannedCheckInDate)) AS planned_room_nights,
    SUM(rp.numGuests) AS expected_guests
FROM reservation r
JOIN reservation_preference rp ON rp.reservationId = r.reservationId
GROUP BY r.reservationStatus
ORDER BY reservation_count DESC, r.reservationStatus;

-- 2. On which check-in dates is guest arrival demand the highest?
SELECT
    r.plannedCheckInDate,
    COUNT(*) AS arrivals,
    SUM(rp.numGuests) AS expected_guests,
    SUM(julianday(r.plannedCheckOutDate) - julianday(r.plannedCheckInDate)) AS expected_room_nights
FROM reservation r
JOIN reservation_preference rp ON rp.reservationId = r.reservationId
GROUP BY r.plannedCheckInDate
ORDER BY r.plannedCheckInDate;

-- 3. How is guest-room inventory distributed across wings, and how convenient is each wing for parking or pool access?
SELECT
    b.buildingName,
    w.wingCode,
    COUNT(*) AS room_count,
    SUM(CASE WHEN w.nearParking = 1 THEN 1 ELSE 0 END) AS near_parking_rooms,
    SUM(CASE WHEN w.nearIndoorPool = 1 THEN 1 ELSE 0 END) AS near_indoor_pool_rooms,
    SUM(CASE WHEN w.nearOutdoorPool = 1 THEN 1 ELSE 0 END) AS near_outdoor_pool_rooms
FROM room r
JOIN level l ON l.levelId = r.levelId
JOIN wing w ON w.wingId = l.wingId
JOIN building b ON b.buildingId = w.buildingId
GROUP BY b.buildingName, w.wingCode
ORDER BY room_count DESC, b.buildingName, w.wingCode;

-- 4. Which wing offers the highest average nightly rate and average sleeping capacity for guest rooms?
SELECT
    b.buildingName,
    w.wingCode,
    ROUND(AVG(rc.baseRate), 2) AS avg_nightly_rate,
    ROUND(AVG(rc.capacity), 2) AS avg_sleeping_capacity,
    COUNT(*) AS sleeping_rooms
FROM room_capability rc
JOIN capability_type ct ON ct.capabilityTypeId = rc.capabilityTypeId
JOIN room r ON r.roomId = rc.roomId
JOIN level l ON l.levelId = r.levelId
JOIN wing w ON w.wingId = l.wingId
JOIN building b ON b.buildingId = w.buildingId
WHERE ct.capabilityCode = 'SLEEPING'
GROUP BY b.buildingName, w.wingCode
ORDER BY avg_nightly_rate DESC, avg_sleeping_capacity DESC;

-- 5. What bed sizes are most common across guest rooms?
SELECT
    bt.size AS bed_size,
    COUNT(DISTINCT rb.roomId) AS rooms_with_bed_type,
    SUM(rb.quantity) AS total_beds
FROM room_bed rb
JOIN bed_type bt ON bt.bedTypeId = rb.bedTypeId
JOIN room r ON r.roomId = rb.roomId
GROUP BY bt.size
ORDER BY rooms_with_bed_type DESC, total_beds DESC, bed_size;

-- 6. What room preference patterns appear most often among active reservations?
SELECT
    CASE
        WHEN rp.smokingPref = 0 THEN 'Non-smoking'
        WHEN rp.smokingPref = 1 THEN 'Smoking'
        ELSE 'No smoking preference'
    END AS smoking_preference,
    COUNT(*) AS reservation_count
FROM reservation_preference rp
JOIN reservation r ON r.reservationId = rp.reservationId
WHERE r.reservationStatus IN ('BOOKED', 'CHECKED_IN')
GROUP BY smoking_preference
ORDER BY reservation_count DESC, smoking_preference;

-- 7. How are active stays distributed across wings right now?
SELECT
    b.buildingName,
    w.wingCode,
    COUNT(DISTINCT sra.stayAssignmentId) AS active_stays,
    COUNT(DISTINCT srg.guestId) AS assigned_guests
FROM stay_room_assignment sra
JOIN room r ON r.roomId = sra.roomId
JOIN level l ON l.levelId = r.levelId
JOIN wing w ON w.wingId = l.wingId
JOIN building b ON b.buildingId = w.buildingId
LEFT JOIN stay_room_guest srg ON srg.stayAssignmentId = sra.stayAssignmentId
WHERE sra.assignmentStatus IN ('RESERVED', 'OCCUPIED')
GROUP BY b.buildingName, w.wingCode
ORDER BY active_stays DESC, assigned_guests DESC, b.buildingName, w.wingCode;


-- 8. For each account, how much has been charged, paid, and is still outstanding?
WITH charge_summary AS (
    SELECT
        accountId,
        SUM(amount) AS total_charges
    FROM charge
    GROUP BY accountId
),
payment_summary AS (
    SELECT
        accountId,
        SUM(amount) AS total_payments
    FROM payment
    GROUP BY accountId
)
SELECT
    a.accountId,
    a.accountName,
    COALESCE(cs.total_charges, 0) AS total_charges,
    COALESCE(ps.total_payments, 0) AS total_payments,
    COALESCE(cs.total_charges, 0) - COALESCE(ps.total_payments, 0) AS balance_due
FROM account a
LEFT JOIN charge_summary cs ON cs.accountId = a.accountId
LEFT JOIN payment_summary ps ON ps.accountId = a.accountId
ORDER BY balance_due DESC, a.accountId;

-- 9. Which charge categories contribute the largest share of total revenue?
SELECT
    c.chargeType,
    COUNT(*) AS charge_lines,
    ROUND(SUM(c.amount), 2) AS total_amount,
    ROUND(AVG(c.amount), 2) AS avg_charge_amount,
    ROUND(100.0 * SUM(c.amount) / (SELECT SUM(amount) FROM charge), 1) AS pct_of_total_revenue
FROM charge c
GROUP BY c.chargeType
ORDER BY total_amount DESC, c.chargeType;

-- 10. Which event time slots are used the most, and how often are they for dining?
SELECT
    eru.usageSlot,
    COUNT(*) AS room_bookings,
    COUNT(DISTINCT eru.eventId) AS events_using_slot,
    SUM(CASE WHEN eru.isEatingUsage = 1 THEN 1 ELSE 0 END) AS dining_bookings
FROM event_room_usage eru
JOIN event e ON e.eventId = eru.eventId
GROUP BY eru.usageSlot
ORDER BY room_bookings DESC, eru.usageSlot;
