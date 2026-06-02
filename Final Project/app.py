from datetime import date, datetime, timedelta
from flask import Flask, redirect, render_template, request, url_for
import os
import sqlite3
from pathlib import Path
from werkzeug.exceptions import HTTPException

app = Flask(__name__)

BASE_DIR = Path(__file__).resolve().parent
DATABASE = BASE_DIR / "last_resort.db"
ROOM_STATUS_TYPES = [
    "OCCUPIED",
    "DIRTY",
    "READY",
    "RENOVATION",
    "RECONSTRUCTION",
    "OUT_OF_SERVICE",
]
USAGE_SLOT_TYPES = [
    "BREAKFAST",
    "MORNING",
    "LUNCH",
    "AFTERNOON",
    "SUPPER",
    "EVENING",
    "NIGHT",
]
RESERVATION_STATUS_TYPES = ["BOOKED", "CHECKED_IN", "CHECKED_OUT", "CANCELLED"]
ASSIGNMENT_STATUS_TYPES = ["RESERVED", "OCCUPIED", "RELEASED"]
OCCUPANT_ROLE_TYPES = ["PRIMARY", "SHARER"]
ACCOUNT_STATUS_TYPES = ["OPEN", "CLOSED", "VOID"]
RESPONSIBILITY_TYPES = ["FULL", "SPLIT", "BACKUP"]
CHARGE_TYPES = [
    "ROOM_RATE",
    "ROOM_SURCHARGE",
    "PHONE",
    "ROOM_SERVICE",
    "BUSINESS_SERVICE",
    "RETAIL",
    "HEALTH_CLUB",
    "MEETING_ROOM",
    "FOOD_BEVERAGE",
    "OTHER",
]
BLOCKED_ROOM_STATUS_TYPES = {
    "OCCUPIED",
    "DIRTY",
    "RENOVATION",
    "RECONSTRUCTION",
    "OUT_OF_SERVICE",
}


def get_current_date():
    return date.today().isoformat()


def get_date_window():
    snapshot_date = get_current_date()
    upcoming_start = snapshot_date
    upcoming_end = (date.fromisoformat(snapshot_date) + timedelta(days=6)).isoformat()
    return {
        "snapshotDate": snapshot_date,
        "snapshotTimestamp": f"{snapshot_date} 23:59:59",
        "upcomingStart": upcoming_start,
        "upcomingEnd": upcoming_end,
    }


def get_db_connection():
    conn = sqlite3.connect(DATABASE)
    conn.execute("PRAGMA foreign_keys = ON")
    conn.row_factory = sqlite3.Row
    return conn


def get_current_timestamp():
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def clean_text(value):
    if value is None:
        return ""
    return value.strip()


def optional_text(value):
    value = clean_text(value)
    if value:
        return value
    return None


def parse_checkbox(value):
    if value in ("1", "on", "true", "yes"):
        return 1
    return 0


def parse_optional_int(value):
    value = clean_text(value)
    if not value:
        return None
    return int(value)


def parse_optional_float(value):
    value = clean_text(value)
    if not value:
        return None
    return float(value)


def parse_datetime_input(value):
    value = clean_text(value)
    if not value:
        return None

    value = value.replace("T", " ")
    if len(value) == 16:
        value += ":00"
    return value


def parse_date_input(value):
    value = clean_text(value)
    if not value:
        return None
    return value[:10]


def format_datetime_input(value):
    if not value:
        return ""
    return value[:16].replace(" ", "T")


def format_date_input(value):
    if not value:
        return ""
    return value[:10]


def get_next_id(conn, table_name, column_name):
    row = conn.execute(
        f"SELECT COALESCE(MAX({column_name}), 0) + 1 FROM {table_name}"
    ).fetchone()
    return row[0]


def get_page_notice():
    return clean_text(request.args.get("message")), clean_text(request.args.get("messageType")) or "success"


def redirect_with_message(endpoint, message, message_type="success", **params):
    clean_params = {}
    for key, value in params.items():
        if value is None or value == "":
            continue
        clean_params[key] = value

    clean_params["message"] = message
    clean_params["messageType"] = message_type
    return redirect(url_for(endpoint, **clean_params))


def choose_selected_id(rows, requested_id, key_name):
    if not rows:
        return None

    valid_ids = {row[key_name] for row in rows}
    if requested_id in valid_ids:
        return requested_id

    return rows[0][key_name]


def matches_name_or_id(display_name, row_id, search_text):
    if not search_text:
        return True

    if search_text.isdigit():
        return row_id == int(search_text)

    return search_text.lower() in display_name.lower()


def format_person_name(first_name, last_name):
    if first_name and last_name:
        return f"{first_name} {last_name}"
    return None


def format_party_name(first_name, last_name, organization_name):
    person_name = format_person_name(first_name, last_name)
    if person_name:
        return person_name
    if organization_name:
        return organization_name
    return "Unknown"


def normalize_room_status(status_type):
    if status_type == "AVAILABLE":
        return "READY"
    return status_type


def list_status_dates(start_date, end_date):
    current_day = date.fromisoformat(start_date)
    final_day = date.fromisoformat(end_date)
    date_list = []

    while current_day <= final_day:
        date_list.append(current_day.isoformat())
        current_day += timedelta(days=1)

    return date_list


def load_status_rows_for_window(conn, window_start, window_end):
    return conn.execute(
        """
        SELECT statusId, roomId, statusType, startTime, endTime
        FROM room_status
        WHERE startTime <= ?
          AND endTime >= ?
        ORDER BY roomId, startTime, statusId
        """,
        (window_end, window_start),
    ).fetchall()


def group_status_rows_by_room(status_rows):
    status_map = {}
    for row in status_rows:
        room_rows = status_map.setdefault(row["roomId"], [])
        room_rows.append(row)
    return status_map


def get_effective_room_status(status_rows, status_date):
    chosen_status = "READY"
    chosen_start = ""
    chosen_id = -1

    for row in status_rows:
        if row["startTime"] > status_date:
            continue

        if row["endTime"] < status_date:
            continue

        if row["startTime"] > chosen_start:
            chosen_status = normalize_room_status(row["statusType"])
            chosen_start = row["startTime"]
            chosen_id = row["statusId"]
        elif row["startTime"] == chosen_start and row["statusId"] > chosen_id:
            chosen_status = normalize_room_status(row["statusType"])
            chosen_id = row["statusId"]

    return chosen_status


def load_room_status_date_range(conn):
    row = conn.execute(
        """
        SELECT
            MIN(startTime) AS firstStatusDate,
            MAX(endTime) AS lastStatusDate
        FROM room_status
        """
    ).fetchone()

    if row is None:
        return None, None

    return row["firstStatusDate"], row["lastStatusDate"]


def load_current_guests(conn, snapshot_date, upcoming_start, upcoming_end):
    current_guest_rows = conn.execute(
        """
        SELECT
            g.guestId,
            p.firstName || ' ' || p.lastName AS guestName,
            r.roomNum,
            w.wingCode,
            group_concat(DISTINCT o.organizationName) AS affiliations,
            group_concat(DISTINCT e.eventName) AS upcomingEvents
        FROM stay_room_assignment sra
        JOIN stay_room_guest srg ON srg.stayAssignmentId = sra.stayAssignmentId
        JOIN guest g ON g.guestId = srg.guestId
        JOIN person p ON p.personId = g.personId
        JOIN room r ON r.roomId = sra.roomId
        JOIN level l ON l.levelId = r.levelId
        JOIN wing w ON w.wingId = l.wingId
        LEFT JOIN organization_member om ON om.personId = p.personId
        LEFT JOIN organization o ON o.organizationId = om.organizationId
        LEFT JOIN event_guest eg ON eg.guestId = g.guestId
        LEFT JOIN event e ON e.eventId = eg.eventId
            AND e.startDate BETWEEN ? AND ?
        WHERE sra.assignedStartDate <= ?
          AND COALESCE(sra.assignedEndDate, '9999-12-31') > ?
          AND sra.assignmentStatus = 'OCCUPIED'
        GROUP BY g.guestId, p.firstName, p.lastName, r.roomNum, w.wingCode
        ORDER BY w.wingCode, r.roomNum, guestName
        """,
        (upcoming_start, upcoming_end, snapshot_date, snapshot_date),
    ).fetchall()

    current_guests = []
    for row in current_guest_rows:
        current_guests.append(
            {
                "guestId": row["guestId"],
                "guestName": row["guestName"],
                "roomNum": row["roomNum"],
                "wingCode": row["wingCode"],
                "affiliations": row["affiliations"] or "Independent",
                "upcomingEvents": row["upcomingEvents"] or "None",
            }
        )

    return current_guests


def format_event_date_label(start_date, end_date):
    if start_date == end_date:
        return start_date
    return f"{start_date} to {end_date}"


def load_upcoming_events(conn, snapshot_date, upcoming_end):
    active_event_rows = conn.execute(
        """
        SELECT
            e.eventId,
            e.eventName,
            e.startDate,
            e.endDate,
            host_person.firstName AS hostFirstName,
            host_person.lastName AS hostLastName,
            host_org.organizationName AS hostOrgName,
            group_concat(DISTINCT r.roomNum || ' (' || eru.usageSlot || ')') AS scheduledRooms
        FROM event e
        LEFT JOIN party hp ON hp.partyId = e.hostPartyId
        LEFT JOIN person host_person ON host_person.personId = hp.personId
        LEFT JOIN organization host_org ON host_org.organizationId = hp.organizationId
        LEFT JOIN event_room_usage eru ON eru.eventId = e.eventId
        LEFT JOIN room r ON r.roomId = eru.roomId
        WHERE e.startDate <= ?
          AND e.endDate >= ?
        GROUP BY
            e.eventId,
            e.eventName,
            e.startDate,
            e.endDate,
            host_person.firstName,
            host_person.lastName,
            host_org.organizationName
        ORDER BY e.startDate, e.eventName
        """,
        (snapshot_date, snapshot_date),
    ).fetchall()

    future_event_rows = conn.execute(
        """
        SELECT
            e.eventId,
            e.eventName,
            e.startDate,
            e.endDate,
            host_person.firstName AS hostFirstName,
            host_person.lastName AS hostLastName,
            host_org.organizationName AS hostOrgName,
            group_concat(DISTINCT r.roomNum || ' (' || eru.usageSlot || ')') AS scheduledRooms
        FROM event e
        LEFT JOIN party hp ON hp.partyId = e.hostPartyId
        LEFT JOIN person host_person ON host_person.personId = hp.personId
        LEFT JOIN organization host_org ON host_org.organizationId = hp.organizationId
        LEFT JOIN event_room_usage eru ON eru.eventId = e.eventId
        LEFT JOIN room r ON r.roomId = eru.roomId
        WHERE e.startDate > ?
          AND e.startDate <= ?
        GROUP BY
            e.eventId,
            e.eventName,
            e.startDate,
            e.endDate,
            host_person.firstName,
            host_person.lastName,
            host_org.organizationName
        ORDER BY e.startDate, e.eventName
        """,
        (snapshot_date, upcoming_end),
    ).fetchall()

    upcoming_events = []
    for row in active_event_rows:
        upcoming_events.append(
            {
                "eventId": row["eventId"],
                "eventName": row["eventName"],
                "dateLabel": format_event_date_label(row["startDate"], row["endDate"]),
                "hostName": format_party_name(
                    row["hostFirstName"],
                    row["hostLastName"],
                    row["hostOrgName"],
                ),
                "scheduledRooms": row["scheduledRooms"] or "No rooms assigned yet",
                "eventStatus": "Active Today",
            }
        )

    for row in future_event_rows:
        upcoming_events.append(
            {
                "eventId": row["eventId"],
                "eventName": row["eventName"],
                "dateLabel": format_event_date_label(row["startDate"], row["endDate"]),
                "hostName": format_party_name(
                    row["hostFirstName"],
                    row["hostLastName"],
                    row["hostOrgName"],
                ),
                "scheduledRooms": row["scheduledRooms"] or "No rooms assigned yet",
                "eventStatus": "Upcoming",
            }
        )

    return upcoming_events


def load_event_guest_counts(conn, upcoming_start, upcoming_end):
    return conn.execute(
        """
        SELECT
            e.eventId,
            e.eventName,
            e.startDate,
            COUNT(DISTINCT eg.guestId) AS linkedGuests,
            COALESCE(e.estimatedGuestCount, 0) AS estimatedGuestCount
        FROM event e
        LEFT JOIN event_guest eg ON eg.eventId = e.eventId
        WHERE e.startDate BETWEEN ? AND ?
        GROUP BY e.eventId, e.eventName, e.startDate, e.estimatedGuestCount
        ORDER BY e.startDate, e.eventName
        """,
        (upcoming_start, upcoming_end),
    ).fetchall()


def load_home_summary(conn, snapshot_date, snapshot_timestamp, upcoming_start, upcoming_end):
    current_guest_count = conn.execute(
        """
        SELECT COUNT(DISTINCT srg.guestId)
        FROM stay_room_assignment sra
        JOIN stay_room_guest srg ON srg.stayAssignmentId = sra.stayAssignmentId
        WHERE sra.assignedStartDate <= ?
          AND COALESCE(sra.assignedEndDate, '9999-12-31') > ?
          AND sra.assignmentStatus = 'OCCUPIED'
        """,
        (snapshot_date, snapshot_date),
    ).fetchone()[0]

    upcoming_event_count = conn.execute(
        """
        SELECT COUNT(*)
        FROM event
        WHERE startDate BETWEEN ? AND ?
        """,
        (upcoming_start, upcoming_end),
    ).fetchone()[0]

    open_account_count = conn.execute(
        "SELECT COUNT(*) FROM account WHERE accountStatus = 'OPEN'"
    ).fetchone()[0]

    maintenance_count = conn.execute(
        """
        SELECT COUNT(*)
        FROM room_status
        WHERE statusType IN ('RENOVATION', 'RECONSTRUCTION', 'OUT_OF_SERVICE')
          AND startTime <= ?
          AND endTime >= ?
        """,
        (snapshot_date, snapshot_date),
    ).fetchone()[0]

    return [
        {"label": "Current Guests", "value": current_guest_count},
        {"label": "Upcoming Events", "value": upcoming_event_count},
        {"label": "Open Accounts", "value": open_account_count},
        {"label": "Maintenance Rooms", "value": maintenance_count},
    ]


def load_room_page_data(conn, start_date, end_date, status_date):
    first_status_date, last_status_date = load_room_status_date_range(conn)

    all_room_rows = conn.execute(
        """
        SELECT roomId
        FROM room
        ORDER BY roomId
        """
    ).fetchall()

    room_rows = conn.execute(
        """
        SELECT
            r.roomId,
            r.roomNum,
            w.wingCode,
            ct.capabilityCode,
            rc.capacity,
            rc.baseRate
        FROM room r
        JOIN level l ON l.levelId = r.levelId
        JOIN wing w ON w.wingId = l.wingId
        JOIN room_capability rc ON rc.roomId = r.roomId
        JOIN capability_type ct ON ct.capabilityTypeId = rc.capabilityTypeId
        WHERE ct.capabilityCode IN ('SLEEPING', 'SUITE')
        ORDER BY w.wingCode, r.roomNum
        """
    ).fetchall()

    current_status_map = {}
    for row in all_room_rows:
        current_status_map[row["roomId"]] = "READY"

    if (
        first_status_date is not None
        and last_status_date is not None
        and first_status_date <= status_date <= last_status_date
    ):
        current_status_rows = load_status_rows_for_window(
            conn,
            status_date,
            status_date,
        )
        current_status_by_room = group_status_rows_by_room(current_status_rows)
        for row in all_room_rows:
            room_id = row["roomId"]
            current_status_map[room_id] = get_effective_room_status(
                current_status_by_room.get(room_id, []),
                status_date,
            )

    blocked_stay_rows = conn.execute(
        """
        SELECT DISTINCT roomId
        FROM stay_room_assignment
        WHERE assignmentStatus IN ('RESERVED', 'OCCUPIED')
          AND assignedStartDate <= ?
          AND COALESCE(assignedEndDate, '9999-12-31') > ?
        """,
        (end_date, start_date),
    ).fetchall()

    blocked_room_ids = {row["roomId"] for row in blocked_stay_rows}
    if first_status_date is not None and last_status_date is not None:
        if not (end_date < first_status_date or start_date > last_status_date):
            status_block_start = start_date
            status_block_end = end_date

            if status_block_start < first_status_date:
                status_block_start = first_status_date
            if status_block_end > last_status_date:
                status_block_end = last_status_date

            search_dates = list_status_dates(status_block_start, status_block_end)
            status_window_rows = load_status_rows_for_window(
                conn,
                status_block_start,
                status_block_end,
            )
            status_rows_by_room = group_status_rows_by_room(status_window_rows)

            for row in room_rows:
                room_id = row["roomId"]
                room_status_rows = status_rows_by_room.get(room_id, [])

                for search_date in search_dates:
                    effective_status = get_effective_room_status(
                        room_status_rows,
                        search_date,
                    )
                    if effective_status in BLOCKED_ROOM_STATUS_TYPES:
                        blocked_room_ids.add(room_id)
                        break

    available_rooms = []
    for row in room_rows:
        if row["roomId"] in blocked_room_ids:
            continue

        room_use = "Suite"
        if row["capabilityCode"] == "SLEEPING":
            room_use = "Sleeping"

        available_rooms.append(
            {
                "roomNum": row["roomNum"],
                "wingCode": row["wingCode"],
                "roomUse": room_use,
                "capacity": row["capacity"],
                "baseRate": row["baseRate"],
                "currentStatus": current_status_map.get(row["roomId"], "READY"),
            }
        )

    room_status_counts = {}
    for row in all_room_rows:
        status_type = current_status_map.get(row["roomId"], "READY")
        if status_type not in room_status_counts:
            room_status_counts[status_type] = 0
        room_status_counts[status_type] += 1

    room_status_summary = []
    for status_type, room_count in room_status_counts.items():
        room_status_summary.append(
            {
                "statusType": status_type,
                "roomCount": room_count,
            }
        )

    room_status_summary.sort(key=lambda row: (-row["roomCount"], row["statusType"]))

    reservation_trend_rows = conn.execute(
        """
        SELECT
            substr(r.plannedCheckInDate, 1, 7) AS stayMonth,
            COUNT(*) AS reservationCount,
            ROUND(SUM(julianday(r.plannedCheckOutDate) - julianday(r.plannedCheckInDate)), 1) AS roomNights,
            SUM(rp.numGuests) AS expectedGuests
        FROM reservation r
        JOIN reservation_preference rp ON rp.reservationId = r.reservationId
        WHERE r.reservationStatus <> 'CANCELLED'
        GROUP BY stayMonth
        ORDER BY stayMonth
        """
    ).fetchall()

    max_reservation_count = 0
    for row in reservation_trend_rows:
        if row["reservationCount"] > max_reservation_count:
            max_reservation_count = row["reservationCount"]

    reservation_trends = []
    for row in reservation_trend_rows:
        bar_width = 0
        if max_reservation_count > 0:
            bar_width = int(row["reservationCount"] * 100 / max_reservation_count)

        reservation_trends.append(
            {
                "stayMonth": row["stayMonth"],
                "reservationCount": row["reservationCount"],
                "roomNights": row["roomNights"],
                "expectedGuests": row["expectedGuests"],
                "barWidth": bar_width,
            }
        )

    maintenance_count = 0
    for row in room_status_summary:
        if row["statusType"] in {"RENOVATION", "RECONSTRUCTION", "OUT_OF_SERVICE"}:
            maintenance_count += row["roomCount"]

    return available_rooms, room_status_summary, reservation_trends, maintenance_count


def load_account_balances(conn):
    account_rows = conn.execute(
        """
        SELECT accountId, accountName, accountStatus
        FROM account
        ORDER BY accountId
        """
    ).fetchall()

    charge_total_rows = conn.execute(
        """
        SELECT accountId, ROUND(SUM(amount), 2) AS totalCharges
        FROM charge
        GROUP BY accountId
        """
    ).fetchall()
    charge_totals = {row["accountId"]: row["totalCharges"] for row in charge_total_rows}

    payment_total_rows = conn.execute(
        """
        SELECT accountId, ROUND(SUM(amount), 2) AS totalPayments
        FROM payment
        GROUP BY accountId
        """
    ).fetchall()
    payment_totals = {row["accountId"]: row["totalPayments"] for row in payment_total_rows}

    responsibility_rows = conn.execute(
        """
        SELECT
            ar.accountId,
            ar.responsibilityType,
            ar.responsibilityPercent,
            person.firstName,
            person.lastName,
            organization.organizationName
        FROM account_responsibility ar
        JOIN party p ON p.partyId = ar.partyId
        LEFT JOIN person ON person.personId = p.personId
        LEFT JOIN organization ON organization.organizationId = p.organizationId
        ORDER BY ar.accountId
        """
    ).fetchall()

    responsibility_map = {}
    for row in responsibility_rows:
        label = format_party_name(row["firstName"], row["lastName"], row["organizationName"])
        if row["responsibilityPercent"] is not None:
            label += f" ({row['responsibilityType']} {row['responsibilityPercent']:.0f}%)"
        else:
            label += f" ({row['responsibilityType']})"
        responsibility_map.setdefault(row["accountId"], []).append(label)

    account_balances = []
    for row in account_rows:
        account_id = row["accountId"]
        total_charges = charge_totals.get(account_id, 0)
        total_payments = payment_totals.get(account_id, 0)
        account_balances.append(
            {
                "accountId": account_id,
                "accountName": row["accountName"],
                "accountStatus": row["accountStatus"],
                "totalCharges": total_charges,
                "totalPayments": total_payments,
                "balanceDue": round(total_charges - total_payments, 2),
                "responsibleParties": ", ".join(
                    responsibility_map.get(account_id, ["No responsible party listed"])
                ),
            }
        )

    account_balances.sort(
        key=lambda row: (
            row["accountStatus"] != "OPEN",
            -row["balanceDue"],
            row["accountId"],
        )
    )
    return account_balances


def load_revenue_breakdown(conn):
    total_revenue = conn.execute("SELECT COALESCE(SUM(amount), 0) FROM charge").fetchone()[0]
    revenue_rows = conn.execute(
        """
        SELECT
            chargeType,
            COUNT(*) AS chargeLines,
            ROUND(SUM(amount), 2) AS totalAmount,
            ROUND(AVG(amount), 2) AS avgChargeAmount
        FROM charge
        GROUP BY chargeType
        ORDER BY totalAmount DESC, chargeType
        """
    ).fetchall()

    revenue_breakdown = []
    for row in revenue_rows:
        pct_of_revenue = 0
        if total_revenue:
            pct_of_revenue = round(100.0 * row["totalAmount"] / total_revenue, 1)
        revenue_breakdown.append(
            {
                "chargeType": row["chargeType"],
                "chargeLines": row["chargeLines"],
                "totalAmount": row["totalAmount"],
                "avgChargeAmount": row["avgChargeAmount"],
                "pctOfRevenue": pct_of_revenue,
            }
        )

    return revenue_breakdown


def load_guest_contacts(conn):
    guest_rows = conn.execute(
        """
        SELECT
            g.guestId,
            p.firstName || ' ' || p.lastName AS guestName,
            g.isConfidential
        FROM guest g
        JOIN person p ON p.personId = g.personId
        ORDER BY guestName
        """
    ).fetchall()

    swipe_rows = conn.execute(
        """
        SELECT
            csl.guestId,
            csl.swipeTime,
            r.readerName,
            r.locationDescription
        FROM card_swipe_log csl
        JOIN reader r ON r.readerId = csl.readerId
        WHERE csl.guestId IS NOT NULL
        ORDER BY csl.guestId, csl.swipeTime DESC
        """
    ).fetchall()
    latest_swipe_by_guest = {}
    for row in swipe_rows:
        if row["guestId"] not in latest_swipe_by_guest:
            latest_swipe_by_guest[row["guestId"]] = dict(row)

    message_rows = conn.execute(
        """
        SELECT guestId, messageTime, messageContent
        FROM guest_message
        ORDER BY guestId, messageTime DESC
        """
    ).fetchall()
    latest_message_by_guest = {}
    for row in message_rows:
        if row["guestId"] not in latest_message_by_guest:
            latest_message_by_guest[row["guestId"]] = dict(row)

    guest_contacts = []
    for row in guest_rows:
        guest_id = row["guestId"]
        swipe = latest_swipe_by_guest.get(guest_id)
        message = latest_message_by_guest.get(guest_id)

        if row["isConfidential"] == 1:
            last_known_location = "Confidential - contact through front desk"
        elif swipe is None:
            last_known_location = "No recent swipe recorded"
        else:
            last_known_location = f"{swipe['readerName']} - {swipe['locationDescription']}"

        guest_contacts.append(
            {
                "guestId": guest_id,
                "guestName": row["guestName"],
                "isConfidential": row["isConfidential"],
                "lastSwipeTime": swipe["swipeTime"] if swipe else None,
                "lastKnownLocation": last_known_location,
                "lastMessageTime": message["messageTime"] if message else None,
                "messageContent": message["messageContent"] if message else "No recent guest message",
                "sortTime": max(
                    swipe["swipeTime"] if swipe else "",
                    message["messageTime"] if message else "",
                ),
            }
        )

    guest_contacts_with_updates = []
    guest_contacts_without_updates = []

    for row in guest_contacts:
        if row["sortTime"]:
            guest_contacts_with_updates.append(row)
        else:
            guest_contacts_without_updates.append(row)

    guest_contacts_with_updates.sort(
        key=lambda row: (row["sortTime"], row["guestName"]),
        reverse=True,
    )
    guest_contacts_without_updates.sort(key=lambda row: row["guestName"])
    return guest_contacts_with_updates + guest_contacts_without_updates


def load_party_options(conn):
    party_rows = conn.execute(
        """
        SELECT
            p.partyId,
            p.partyType,
            person.firstName,
            person.lastName,
            organization.organizationName
        FROM party p
        LEFT JOIN person ON person.personId = p.personId
        LEFT JOIN organization ON organization.organizationId = p.organizationId
        ORDER BY p.partyType, organization.organizationName, person.lastName, person.firstName
        """
    ).fetchall()

    party_options = []
    for row in party_rows:
        label = format_party_name(row["firstName"], row["lastName"], row["organizationName"])
        if row["partyType"] == "ORGANIZATION":
            label += " (Organization)"
        else:
            label += " (Person)"
        party_options.append(
            {
                "partyId": row["partyId"],
                "label": label,
            }
        )

    party_options.sort(key=lambda row: row["label"])
    return party_options


def load_guest_options(conn):
    guest_rows = conn.execute(
        """
        SELECT
            g.guestId,
            p.firstName || ' ' || p.lastName AS guestName
        FROM guest g
        JOIN person p ON p.personId = g.personId
        ORDER BY guestName
        """
    ).fetchall()

    guest_options = []
    for row in guest_rows:
        guest_options.append(
            {
                "guestId": row["guestId"],
                "guestName": row["guestName"],
            }
        )

    return guest_options


def load_event_room_options(conn):
    room_rows = conn.execute(
        """
        SELECT DISTINCT r.roomId, r.roomNum
        FROM room r
        JOIN room_capability rc ON rc.roomId = r.roomId
        JOIN capability_type ct ON ct.capabilityTypeId = rc.capabilityTypeId
        WHERE ct.capabilityCode IN ('MEETING', 'SUITE')
        ORDER BY r.roomNum
        """
    ).fetchall()

    room_options = []
    for row in room_rows:
        room_options.append(
            {
                "roomId": row["roomId"],
                "roomNum": row["roomNum"],
            }
        )

    return room_options


def load_room_options(conn):
    room_rows = conn.execute(
        """
        SELECT roomId, roomNum
        FROM room
        ORDER BY roomNum
        """
    ).fetchall()

    room_options = []
    for row in room_rows:
        room_options.append(
            {
                "roomId": row["roomId"],
                "roomNum": row["roomNum"],
            }
        )

    return room_options


def load_employee_options(conn):
    employee_rows = conn.execute(
        """
        SELECT
            e.employeeId,
            p.firstName || ' ' || p.lastName AS employeeName,
            e.jobTitle
        FROM employee e
        JOIN person p ON p.personId = e.personId
        ORDER BY employeeName
        """
    ).fetchall()

    employee_options = []
    for row in employee_rows:
        employee_options.append(
            {
                "employeeId": row["employeeId"],
                "label": f"{row['employeeName']} ({row['jobTitle']})",
            }
        )

    return employee_options


def load_sleep_room_options(conn):
    room_rows = conn.execute(
        """
        SELECT DISTINCT r.roomId, r.roomNum
        FROM room r
        JOIN room_capability rc ON rc.roomId = r.roomId
        JOIN capability_type ct ON ct.capabilityTypeId = rc.capabilityTypeId
        WHERE ct.capabilityCode IN ('SLEEPING', 'SUITE')
        ORDER BY r.roomNum
        """
    ).fetchall()

    room_options = []
    for row in room_rows:
        room_options.append(
            {
                "roomId": row["roomId"],
                "roomNum": row["roomNum"],
            }
        )

    return room_options


def load_event_options(conn):
    event_rows = conn.execute(
        """
        SELECT eventId, eventName, startDate, endDate
        FROM event
        ORDER BY startDate DESC, eventId DESC
        """
    ).fetchall()

    event_options = []
    for row in event_rows:
        event_options.append(
            {
                "eventId": row["eventId"],
                "label": f"{row['eventName']} ({row['startDate']} to {row['endDate']})",
            }
        )

    return event_options


def ranges_overlap(start_one, end_one, start_two, end_two):
    end_one_value = end_one or "9999-12-31"
    end_two_value = end_two or "9999-12-31"
    return start_one < end_two_value and start_two < end_one_value


def find_room_assignment_conflict(conn, room_id, start_date, end_date, ignore_assignment_id=None):
    assignment_rows = conn.execute(
        """
        SELECT stayAssignmentId, assignedStartDate, assignedEndDate, assignmentStatus
        FROM stay_room_assignment
        WHERE roomId = ?
        ORDER BY assignedStartDate
        """,
        (room_id,),
    ).fetchall()

    for row in assignment_rows:
        if ignore_assignment_id is not None and row["stayAssignmentId"] == ignore_assignment_id:
            continue
        if row["assignmentStatus"] == "RELEASED":
            continue
        if ranges_overlap(
            start_date,
            end_date,
            row["assignedStartDate"],
            row["assignedEndDate"],
        ):
            return row["stayAssignmentId"]

    return None


def load_reservation_rows(conn):
    reservation_rows = conn.execute(
        """
        SELECT
            r.reservationId,
            r.bookedByPartyId,
            r.billingPartyId,
            r.bookingDate,
            r.plannedCheckInDate,
            r.plannedCheckOutDate,
            r.reservationStatus,
            r.advanceDeposit,
            booked_person.firstName AS bookedFirstName,
            booked_person.lastName AS bookedLastName,
            booked_org.organizationName AS bookedOrgName,
            billed_person.firstName AS billedFirstName,
            billed_person.lastName AS billedLastName,
            billed_org.organizationName AS billedOrgName
        FROM reservation r
        JOIN party booked_party ON booked_party.partyId = r.bookedByPartyId
        LEFT JOIN person booked_person ON booked_person.personId = booked_party.personId
        LEFT JOIN organization booked_org ON booked_org.organizationId = booked_party.organizationId
        JOIN party billed_party ON billed_party.partyId = r.billingPartyId
        LEFT JOIN person billed_person ON billed_person.personId = billed_party.personId
        LEFT JOIN organization billed_org ON billed_org.organizationId = billed_party.organizationId
        ORDER BY r.plannedCheckInDate DESC, r.reservationId DESC
        """
    ).fetchall()

    assignment_count_rows = conn.execute(
        """
        SELECT reservationId, COUNT(*) AS assignmentCount
        FROM stay_room_assignment
        GROUP BY reservationId
        """
    ).fetchall()
    assignment_counts = {row["reservationId"]: row["assignmentCount"] for row in assignment_count_rows}

    account_count_rows = conn.execute(
        """
        SELECT reservationId, COUNT(*) AS accountCount
        FROM account
        WHERE reservationId IS NOT NULL
        GROUP BY reservationId
        """
    ).fetchall()
    account_counts = {row["reservationId"]: row["accountCount"] for row in account_count_rows}

    reservation_list = []
    for row in reservation_rows:
        booked_by_label = format_party_name(
            row["bookedFirstName"],
            row["bookedLastName"],
            row["bookedOrgName"],
        )
        billing_label = format_party_name(
            row["billedFirstName"],
            row["billedLastName"],
            row["billedOrgName"],
        )
        reservation_list.append(
            {
                "reservationId": row["reservationId"],
                "bookedByPartyId": row["bookedByPartyId"],
                "billingPartyId": row["billingPartyId"],
                "bookingDate": row["bookingDate"],
                "plannedCheckInDate": row["plannedCheckInDate"],
                "plannedCheckOutDate": row["plannedCheckOutDate"],
                "reservationStatus": row["reservationStatus"],
                "advanceDeposit": row["advanceDeposit"],
                "bookedByLabel": booked_by_label,
                "billingLabel": billing_label,
                "assignmentCount": assignment_counts.get(row["reservationId"], 0),
                "accountCount": account_counts.get(row["reservationId"], 0),
                "displayLabel": f"Reservation {row['reservationId']} - {booked_by_label}",
            }
        )

    return reservation_list


def load_reservation_detail(conn, reservation_id):
    reservation_rows = load_reservation_rows(conn)
    for row in reservation_rows:
        if row["reservationId"] == reservation_id:
            return row
    return None


def load_reservation_assignments(conn, reservation_id):
    assignment_rows = conn.execute(
        """
        SELECT
            sra.stayAssignmentId,
            sra.reservationId,
            sra.roomId,
            r.roomNum,
            sra.assignedStartDate,
            sra.assignedEndDate,
            sra.assignmentStatus
        FROM stay_room_assignment sra
        JOIN room r ON r.roomId = sra.roomId
        WHERE sra.reservationId = ?
        ORDER BY sra.assignedStartDate, sra.stayAssignmentId
        """,
        (reservation_id,),
    ).fetchall()

    guest_rows = conn.execute(
        """
        SELECT
            srg.stayAssignmentId,
            p.firstName || ' ' || p.lastName AS guestName
        FROM stay_room_guest srg
        JOIN guest g ON g.guestId = srg.guestId
        JOIN person p ON p.personId = g.personId
        ORDER BY guestName
        """
    ).fetchall()
    guest_map = {}
    for row in guest_rows:
        guest_map.setdefault(row["stayAssignmentId"], []).append(row["guestName"])

    assignments = []
    for row in assignment_rows:
        assignments.append(
            {
                "stayAssignmentId": row["stayAssignmentId"],
                "reservationId": row["reservationId"],
                "roomId": row["roomId"],
                "roomNum": row["roomNum"],
                "assignedStartDate": row["assignedStartDate"],
                "assignedEndDate": row["assignedEndDate"],
                "assignmentStatus": row["assignmentStatus"],
                "occupantSummary": ", ".join(
                    guest_map.get(row["stayAssignmentId"], [])
                ) or "No guests linked",
            }
        )

    return assignments


def load_assignment_detail(conn, assignment_id):
    row = conn.execute(
        """
        SELECT
            sra.stayAssignmentId,
            sra.reservationId,
            sra.roomId,
            r.roomNum,
            sra.assignedStartDate,
            sra.assignedEndDate,
            sra.assignmentStatus
        FROM stay_room_assignment sra
        JOIN room r ON r.roomId = sra.roomId
        WHERE sra.stayAssignmentId = ?
        """,
        (assignment_id,),
    ).fetchone()

    if row is None:
        return None

    return {
        "stayAssignmentId": row["stayAssignmentId"],
        "reservationId": row["reservationId"],
        "roomId": row["roomId"],
        "roomNum": row["roomNum"],
        "assignedStartDate": row["assignedStartDate"],
        "assignedEndDate": row["assignedEndDate"],
        "assignmentStatus": row["assignmentStatus"],
    }


def load_assignment_guests(conn, assignment_id):
    guest_rows = conn.execute(
        """
        SELECT
            srg.guestId,
            p.firstName || ' ' || p.lastName AS guestName,
            srg.occupantRole
        FROM stay_room_guest srg
        JOIN guest g ON g.guestId = srg.guestId
        JOIN person p ON p.personId = g.personId
        WHERE srg.stayAssignmentId = ?
        ORDER BY srg.occupantRole, guestName
        """,
        (assignment_id,),
    ).fetchall()

    assignment_guests = []
    for row in guest_rows:
        assignment_guests.append(
            {
                "guestId": row["guestId"],
                "guestName": row["guestName"],
                "occupantRole": row["occupantRole"],
            }
        )

    return assignment_guests


def get_reservation_delete_blocker(conn, reservation_id):
    if conn.execute(
        "SELECT 1 FROM stay_room_assignment WHERE reservationId = ? LIMIT 1",
        (reservation_id,),
    ).fetchone() is not None:
        return "This reservation has room assignments and cannot be deleted."

    if conn.execute(
        "SELECT 1 FROM account WHERE reservationId = ? LIMIT 1",
        (reservation_id,),
    ).fetchone() is not None:
        return "This reservation has billing records and cannot be deleted."

    return None


def get_stay_assignment_delete_blocker(conn, assignment_id):
    check_rows = [
        ("SELECT 1 FROM stay_room_guest WHERE stayAssignmentId = ? LIMIT 1", (assignment_id,)),
        ("SELECT 1 FROM charge WHERE stayAssignmentId = ? LIMIT 1", (assignment_id,)),
        ("SELECT 1 FROM room_extension WHERE stayAssignmentId = ? LIMIT 1", (assignment_id,)),
    ]

    for query, params in check_rows:
        if conn.execute(query, params).fetchone() is not None:
            return "This room assignment has linked history and cannot be deleted."

    return None


def load_account_detail(conn, account_id):
    row = conn.execute(
        """
        SELECT
            a.accountId,
            a.reservationId,
            a.eventId,
            a.accountName,
            a.accountStatus,
            a.openedAt,
            a.closedAt
        FROM account a
        WHERE a.accountId = ?
        """,
        (account_id,),
    ).fetchone()

    if row is None:
        return None

    selected_account = dict(row)
    selected_account["openedInput"] = format_datetime_input(row["openedAt"])
    selected_account["closedInput"] = format_datetime_input(row["closedAt"])
    return selected_account


def load_account_responsibilities(conn, account_id):
    responsibility_rows = conn.execute(
        """
        SELECT
            ar.partyId,
            ar.responsibilityType,
            ar.responsibilityPercent,
            person.firstName,
            person.lastName,
            organization.organizationName
        FROM account_responsibility ar
        JOIN party p ON p.partyId = ar.partyId
        LEFT JOIN person ON person.personId = p.personId
        LEFT JOIN organization ON organization.organizationId = p.organizationId
        WHERE ar.accountId = ?
        ORDER BY ar.partyId
        """,
        (account_id,),
    ).fetchall()

    responsibilities = []
    for row in responsibility_rows:
        responsibilities.append(
            {
                "partyId": row["partyId"],
                "partyLabel": format_party_name(
                    row["firstName"],
                    row["lastName"],
                    row["organizationName"],
                ),
                "responsibilityType": row["responsibilityType"],
                "responsibilityPercent": row["responsibilityPercent"],
            }
        )

    return responsibilities


def load_charge_records(conn, account_id):
    charge_rows = conn.execute(
        """
        SELECT
            c.chargeId,
            c.chargeType,
            c.description,
            c.amount,
            c.chargeTime,
            c.usedByGuestId,
            c.stayAssignmentId,
            c.eventId,
            c.createdByEmployeeId,
            person.firstName,
            person.lastName
        FROM charge c
        LEFT JOIN guest g ON g.guestId = c.usedByGuestId
        LEFT JOIN person ON person.personId = g.personId
        WHERE c.accountId = ?
        ORDER BY c.chargeTime, c.chargeId
        """,
        (account_id,),
    ).fetchall()

    charge_records = []
    for row in charge_rows:
        charge_records.append(
            {
                "chargeId": row["chargeId"],
                "chargeType": row["chargeType"],
                "description": row["description"] or "",
                "amount": row["amount"],
                "chargeTime": row["chargeTime"],
                "usedByGuestId": row["usedByGuestId"],
                "usedByGuest": format_person_name(row["firstName"], row["lastName"]) or "Shared or master charge",
                "stayAssignmentId": row["stayAssignmentId"],
                "eventId": row["eventId"],
                "createdByEmployeeId": row["createdByEmployeeId"],
            }
        )

    return charge_records


def load_payment_records(conn, account_id):
    payment_rows = conn.execute(
        """
        SELECT
            p.paymentId,
            p.paidByPartyId,
            p.paymentMethod,
            p.amount,
            p.paymentTime,
            p.referenceNumber,
            person.firstName,
            person.lastName,
            organization.organizationName
        FROM payment p
        JOIN party party_row ON party_row.partyId = p.paidByPartyId
        LEFT JOIN person ON person.personId = party_row.personId
        LEFT JOIN organization ON organization.organizationId = party_row.organizationId
        WHERE p.accountId = ?
        ORDER BY p.paymentTime, p.paymentId
        """,
        (account_id,),
    ).fetchall()

    payment_records = []
    for row in payment_rows:
        payment_records.append(
            {
                "paymentId": row["paymentId"],
                "paidByPartyId": row["paidByPartyId"],
                "paidByLabel": format_party_name(
                    row["firstName"],
                    row["lastName"],
                    row["organizationName"],
                ),
                "paymentMethod": row["paymentMethod"],
                "amount": row["amount"],
                "paymentTime": row["paymentTime"],
                "referenceNumber": row["referenceNumber"] or "",
            }
        )

    return payment_records


def get_account_delete_blocker(conn, account_id):
    check_rows = [
        ("SELECT 1 FROM charge WHERE accountId = ? LIMIT 1", (account_id,)),
        ("SELECT 1 FROM payment WHERE accountId = ? LIMIT 1", (account_id,)),
    ]

    for query, params in check_rows:
        if conn.execute(query, params).fetchone() is not None:
            return "This account already has charges or payments and cannot be deleted."

    return None


def load_event_detail(conn, event_id):
    if event_id is None:
        return None

    row = conn.execute(
        """
        SELECT
            e.eventId,
            e.eventName,
            e.hostPartyId,
            e.billedPartyId,
            e.startDate,
            e.endDate,
            e.estimatedAttendance,
            e.estimatedGuestCount,
            host_person.firstName AS hostFirstName,
            host_person.lastName AS hostLastName,
            host_org.organizationName AS hostOrgName,
            billed_person.firstName AS billedFirstName,
            billed_person.lastName AS billedLastName,
            billed_org.organizationName AS billedOrgName
        FROM event e
        LEFT JOIN party hp ON hp.partyId = e.hostPartyId
        LEFT JOIN person host_person ON host_person.personId = hp.personId
        LEFT JOIN organization host_org ON host_org.organizationId = hp.organizationId
        JOIN party bp ON bp.partyId = e.billedPartyId
        LEFT JOIN person billed_person ON billed_person.personId = bp.personId
        LEFT JOIN organization billed_org ON billed_org.organizationId = bp.organizationId
        WHERE e.eventId = ?
        """,
        (event_id,),
    ).fetchone()

    if row is None:
        return None

    selected_event = dict(row)
    selected_event["hostLabel"] = format_party_name(
        row["hostFirstName"],
        row["hostLastName"],
        row["hostOrgName"],
    )
    selected_event["billedLabel"] = format_party_name(
        row["billedFirstName"],
        row["billedLastName"],
        row["billedOrgName"],
    )
    return selected_event


def load_event_room_records(conn, event_id):
    room_rows = conn.execute(
        """
        SELECT
            eru.usageId,
            eru.roomId,
            r.roomNum,
            eru.usageDate,
            eru.usageSlot,
            eru.isEatingUsage
        FROM event_room_usage eru
        JOIN room r ON r.roomId = eru.roomId
        WHERE eru.eventId = ?
        ORDER BY eru.usageDate, eru.usageSlot, r.roomNum
        """,
        (event_id,),
    ).fetchall()

    room_records = []
    for row in room_rows:
        room_records.append(
            {
                "usageId": row["usageId"],
                "roomId": row["roomId"],
                "roomNum": row["roomNum"],
                "usageDate": row["usageDate"],
                "usageSlot": row["usageSlot"],
                "isEatingUsage": row["isEatingUsage"],
                "isEatingLabel": "Yes" if row["isEatingUsage"] == 1 else "No",
            }
        )

    return room_records


def load_event_guest_records(conn, event_id):
    guest_rows = conn.execute(
        """
        SELECT
            eg.guestId,
            p.firstName || ' ' || p.lastName AS guestName,
            eg.roleName
        FROM event_guest eg
        JOIN guest g ON g.guestId = eg.guestId
        JOIN person p ON p.personId = g.personId
        WHERE eg.eventId = ?
        ORDER BY guestName
        """,
        (event_id,),
    ).fetchall()

    event_guests = []
    for row in guest_rows:
        event_guests.append(
            {
                "guestId": row["guestId"],
                "guestName": row["guestName"],
                "roleName": row["roleName"] or "Attendee",
            }
        )

    return event_guests


def load_guest_messages(conn, guest_id):
    message_rows = conn.execute(
        """
        SELECT messageId, messageContent, messageTime
        FROM guest_message
        WHERE guestId = ?
        ORDER BY messageTime DESC, messageId DESC
        """,
        (guest_id,),
    ).fetchall()

    guest_messages = []
    for row in message_rows:
        guest_messages.append(
            {
                "messageId": row["messageId"],
                "messageContent": row["messageContent"],
                "messageTime": row["messageTime"],
            }
        )

    return guest_messages


def load_room_status_records(conn):
    status_rows = conn.execute(
        """
        SELECT
            rs.statusId,
            rs.roomId,
            r.roomNum,
            rs.statusType,
            rs.startTime,
            rs.endTime,
            rs.employeeId,
            person.firstName,
            person.lastName,
            rs.notes
        FROM room_status rs
        JOIN room r ON r.roomId = rs.roomId
        LEFT JOIN employee e ON e.employeeId = rs.employeeId
        LEFT JOIN person ON person.personId = e.personId
        ORDER BY rs.startTime, rs.statusId
        """
    ).fetchall()

    room_status_records = []
    for row in status_rows:
        employee_name = format_person_name(row["firstName"], row["lastName"])
        if employee_name is None:
            employee_name = "No employee listed"

        room_status_records.append(
            {
                "statusId": row["statusId"],
                "roomId": row["roomId"],
                "roomNum": row["roomNum"],
                "statusType": normalize_room_status(row["statusType"]),
                "startTime": row["startTime"],
                "endTime": row["endTime"],
                "employeeId": row["employeeId"],
                "employeeName": employee_name,
                "notes": row["notes"] or "",
                "startInput": format_date_input(row["startTime"]),
                "endInput": format_date_input(row["endTime"]),
            }
        )

    return room_status_records


def get_guest_delete_blocker(conn, guest_id):
    guest_row = conn.execute(
        """
        SELECT g.personId, p.partyId
        FROM guest g
        LEFT JOIN party p ON p.personId = g.personId AND p.partyType = 'PERSON'
        WHERE g.guestId = ?
        """,
        (guest_id,),
    ).fetchone()

    if guest_row is None:
        return "Guest record was not found."

    person_id = guest_row["personId"]
    party_id = guest_row["partyId"]
    check_rows = [
        ("SELECT 1 FROM stay_room_guest WHERE guestId = ? LIMIT 1", (guest_id,)),
        ("SELECT 1 FROM event_guest WHERE guestId = ? LIMIT 1", (guest_id,)),
        ("SELECT 1 FROM charge WHERE usedByGuestId = ? LIMIT 1", (guest_id,)),
        ("SELECT 1 FROM card_swipe_log WHERE guestId = ? LIMIT 1", (guest_id,)),
        ("SELECT 1 FROM guest_message WHERE guestId = ? LIMIT 1", (guest_id,)),
        ("SELECT 1 FROM organization_member WHERE personId = ? LIMIT 1", (person_id,)),
    ]

    if party_id is not None:
        check_rows.extend(
            [
                ("SELECT 1 FROM reservation WHERE bookedByPartyId = ? OR billingPartyId = ? LIMIT 1", (party_id, party_id)),
                ("SELECT 1 FROM account_responsibility WHERE partyId = ? LIMIT 1", (party_id,)),
                ("SELECT 1 FROM payment WHERE paidByPartyId = ? LIMIT 1", (party_id,)),
                ("SELECT 1 FROM event WHERE hostPartyId = ? OR billedPartyId = ? LIMIT 1", (party_id, party_id)),
            ]
        )

    for query, params in check_rows:
        if conn.execute(query, params).fetchone() is not None:
            return "This guest already has linked history and cannot be deleted."

    return None


def get_event_delete_blocker(conn, event_id):
    account_row = conn.execute(
        "SELECT 1 FROM account WHERE eventId = ? LIMIT 1",
        (event_id,),
    ).fetchone()
    if account_row is not None:
        return "This event has billing records and cannot be deleted."

    return None


@app.route("/", methods=["GET"])
def home():
    date_window = get_date_window()
    conn = get_db_connection()
    summary_cards = load_home_summary(
        conn,
        date_window["snapshotDate"],
        date_window["snapshotTimestamp"],
        date_window["upcomingStart"],
        date_window["upcomingEnd"],
    )
    conn.close()

    return render_template(
        "index.html",
        summaryCards=summary_cards,
        snapshotDate=date_window["snapshotDate"],
        pageTitle="Home",
    )


@app.route("/operations", methods=["GET"])
def operations_page():
    date_window = get_date_window()
    requested_event_id = request.args.get("eventId", type=int)
    page_message, page_message_type = get_page_notice()
    conn = get_db_connection()
    current_guests = load_current_guests(
        conn,
        date_window["snapshotDate"],
        date_window["upcomingStart"],
        date_window["upcomingEnd"],
    )
    upcoming_events = load_upcoming_events(
        conn,
        date_window["snapshotDate"],
        date_window["upcomingEnd"],
    )
    event_guest_counts = load_event_guest_counts(
        conn,
        date_window["upcomingStart"],
        date_window["upcomingEnd"],
    )
    party_options = load_party_options(conn)
    guest_options = load_guest_options(conn)
    event_room_options = load_event_room_options(conn)

    selected_event_id = requested_event_id
    if selected_event_id is None and upcoming_events:
        selected_event_id = upcoming_events[0]["eventId"]

    selected_event = load_event_detail(conn, selected_event_id)
    selected_event_room_usages = []
    selected_event_guests = []
    selected_event_can_delete = False
    if selected_event is not None:
        selected_event_room_usages = load_event_room_records(conn, selected_event_id)
        selected_event_guests = load_event_guest_records(conn, selected_event_id)
        selected_event_can_delete = get_event_delete_blocker(conn, selected_event_id) is None

    conn.close()

    return render_template(
        "operations.html",
        currentGuests=current_guests,
        upcomingEvents=upcoming_events,
        eventGuestCounts=event_guest_counts,
        selectedEvent=selected_event,
        selectedEventId=selected_event_id,
        selectedEventRoomUsages=selected_event_room_usages,
        selectedEventGuests=selected_event_guests,
        selectedEventCanDelete=selected_event_can_delete,
        partyOptions=party_options,
        guestOptions=guest_options,
        eventRoomOptions=event_room_options,
        snapshotDate=date_window["snapshotDate"],
        currentDate=date_window["snapshotDate"],
        pageMessage=page_message,
        pageMessageType=page_message_type,
        pageTitle="Operations",
    )


@app.route("/rooms", methods=["GET"])
def rooms_page():
    current_date = get_current_date()
    requested_status_id = request.args.get("statusId", type=int)
    page_message, page_message_type = get_page_notice()
    start_date = request.args.get("start", current_date).strip() or current_date
    end_date = request.args.get("end", current_date).strip() or current_date
    status_value = request.args.get("status")
    status_date = status_value.strip() if status_value else current_date
    if not status_date:
        status_date = current_date

    if start_date > end_date:
        start_date, end_date = end_date, start_date

    conn = get_db_connection()
    available_rooms, room_status_summary, reservation_trends, maintenance_count = load_room_page_data(
        conn,
        start_date,
        end_date,
        status_date,
    )
    room_status_records = load_room_status_records(conn)
    room_options = load_room_options(conn)
    employee_options = load_employee_options(conn)
    conn.close()

    selected_status_id = choose_selected_id(room_status_records, requested_status_id, "statusId")
    selected_room_status = next(
        (row for row in room_status_records if row["statusId"] == selected_status_id),
        None,
    )

    return render_template(
        "rooms.html",
        availableRooms=available_rooms,
        roomStatusSummary=room_status_summary,
        reservationTrends=reservation_trends,
        roomStatusRecords=room_status_records,
        selectedRoomStatus=selected_room_status,
        selectedStatusId=selected_status_id,
        roomOptions=room_options,
        employeeOptions=employee_options,
        roomStatusTypes=ROOM_STATUS_TYPES,
        maintenanceCount=maintenance_count,
        startDate=start_date,
        endDate=end_date,
        statusDate=status_date,
        snapshotDate=current_date,
        currentDateInput=current_date,
        pageMessage=page_message,
        pageMessageType=page_message_type,
        pageTitle="Room Information",
    )


@app.route("/reservations", methods=["GET"])
def reservations_page():
    current_date = get_current_date()
    requested_reservation_id = request.args.get("reservationId", type=int)
    requested_assignment_id = request.args.get("assignmentId", type=int)
    search_text = request.args.get("search", "").strip()
    page_message, page_message_type = get_page_notice()

    conn = get_db_connection()
    reservation_rows = load_reservation_rows(conn)
    if search_text:
        filtered_rows = []
        for row in reservation_rows:
            if matches_name_or_id(row["displayLabel"], row["reservationId"], search_text):
                filtered_rows.append(row)
        reservation_rows = filtered_rows

    selected_reservation_id = choose_selected_id(
        reservation_rows,
        requested_reservation_id,
        "reservationId",
    )
    selected_reservation = load_reservation_detail(conn, selected_reservation_id)
    selected_assignments = []
    selected_assignment = None
    selected_assignment_guests = []
    selected_assignment_can_delete = False

    if selected_reservation is not None:
        selected_assignments = load_reservation_assignments(conn, selected_reservation_id)
        selected_assignment_id = choose_selected_id(
            selected_assignments,
            requested_assignment_id,
            "stayAssignmentId",
        )
        selected_assignment = load_assignment_detail(conn, selected_assignment_id)
        if selected_assignment is not None:
            selected_assignment_guests = load_assignment_guests(conn, selected_assignment_id)
            selected_assignment_can_delete = (
                get_stay_assignment_delete_blocker(conn, selected_assignment_id) is None
            )

    reservation_can_delete = False
    if selected_reservation is not None:
        reservation_can_delete = (
            get_reservation_delete_blocker(conn, selected_reservation_id) is None
        )

    party_options = load_party_options(conn)
    guest_options = load_guest_options(conn)
    sleep_room_options = load_sleep_room_options(conn)
    conn.close()

    return render_template(
        "reservations.html",
        reservationRows=reservation_rows,
        selectedReservation=selected_reservation,
        selectedReservationId=selected_reservation_id,
        selectedReservationCanDelete=reservation_can_delete,
        selectedAssignments=selected_assignments,
        selectedAssignment=selected_assignment,
        selectedAssignmentId=selected_assignment["stayAssignmentId"] if selected_assignment else None,
        selectedAssignmentGuests=selected_assignment_guests,
        selectedAssignmentCanDelete=selected_assignment_can_delete,
        partyOptions=party_options,
        guestOptions=guest_options,
        sleepRoomOptions=sleep_room_options,
        reservationStatusTypes=RESERVATION_STATUS_TYPES,
        assignmentStatusTypes=ASSIGNMENT_STATUS_TYPES,
        occupantRoleTypes=OCCUPANT_ROLE_TYPES,
        currentDate=current_date,
        searchText=search_text,
        snapshotDate=current_date,
        pageMessage=page_message,
        pageMessageType=page_message_type,
        pageTitle="Reservations",
    )


@app.route("/billing", methods=["GET"])
def billing():
    current_date = get_current_date()
    requested_account_id = request.args.get("accountId", type=int)
    search_text = request.args.get("search", "").strip()
    page_message, page_message_type = get_page_notice()

    conn = get_db_connection()
    account_balances = load_account_balances(conn)
    revenue_breakdown = load_revenue_breakdown(conn)

    if search_text:
        filtered_accounts = []
        for row in account_balances:
            if matches_name_or_id(row["accountName"], row["accountId"], search_text):
                filtered_accounts.append(row)
        account_balances = filtered_accounts

    selected_account_id = choose_selected_id(account_balances, requested_account_id, "accountId")

    selected_account = next(
        (row for row in account_balances if row["accountId"] == selected_account_id),
        None,
    )

    account_detail = None
    account_responsibilities = []
    account_line_items = []
    payment_records = []
    account_can_delete = False
    reservation_options = load_reservation_rows(conn)
    event_options = load_event_options(conn)
    party_options = load_party_options(conn)
    guest_options = load_guest_options(conn)
    employee_options = load_employee_options(conn)
    stay_assignment_options = []

    if selected_account_id is not None:
        account_detail = load_account_detail(conn, selected_account_id)
        account_responsibilities = load_account_responsibilities(conn, selected_account_id)
        account_line_items = load_charge_records(conn, selected_account_id)
        payment_records = load_payment_records(conn, selected_account_id)
        account_can_delete = get_account_delete_blocker(conn, selected_account_id) is None

        if account_detail is not None and account_detail["reservationId"] is not None:
            stay_assignment_options = load_reservation_assignments(
                conn,
                account_detail["reservationId"],
            )

    conn.close()

    if selected_account is not None and account_detail is not None:
        selected_account = {**selected_account, **account_detail}

    return render_template(
        "billing.html",
        accountBalances=account_balances,
        revenueBreakdown=revenue_breakdown,
        selectedAccount=selected_account,
        selectedAccountCanDelete=account_can_delete,
        accountResponsibilities=account_responsibilities,
        accountLineItems=account_line_items,
        paymentRecords=payment_records,
        selectedAccountId=selected_account_id,
        reservationOptions=reservation_options,
        eventOptions=event_options,
        partyOptions=party_options,
        guestOptions=guest_options,
        employeeOptions=employee_options,
        stayAssignmentOptions=stay_assignment_options,
        accountStatusTypes=ACCOUNT_STATUS_TYPES,
        responsibilityTypes=RESPONSIBILITY_TYPES,
        chargeTypes=CHARGE_TYPES,
        currentTimestampInput=format_datetime_input(get_current_timestamp()),
        searchText=search_text,
        snapshotDate=current_date,
        pageMessage=page_message,
        pageMessageType=page_message_type,
        pageTitle="Billing",
    )


@app.route("/guests", methods=["GET"])
def guests_page():
    current_date = get_current_date()
    requested_guest_id = request.args.get("guestId", type=int)
    search_text = request.args.get("search", "").strip()
    page_message, page_message_type = get_page_notice()

    conn = get_db_connection()
    guest_contacts = load_guest_contacts(conn)

    if search_text:
        filtered_guests = []
        for row in guest_contacts:
            if matches_name_or_id(row["guestName"], row["guestId"], search_text):
                filtered_guests.append(row)
        guest_contacts = filtered_guests

    selected_guest_id = choose_selected_id(guest_contacts, requested_guest_id, "guestId")
    selected_guest_contact = next(
        (row for row in guest_contacts if row["guestId"] == selected_guest_id),
        None,
    )

    selected_guest_profile = None
    selected_guest_messages = []
    selected_guest_can_delete = False
    if selected_guest_id is not None:
        profile_row = conn.execute(
            """
            SELECT
                g.guestId,
                p.firstName,
                p.lastName,
                p.firstName || ' ' || p.lastName AS guestName,
                p.phoneNumber,
                p.emailAddress,
                g.pinCode,
                g.isConfidential
            FROM guest g
            JOIN person p ON p.personId = g.personId
            WHERE g.guestId = ?
            """,
            (selected_guest_id,),
        ).fetchone()

        if profile_row is not None:
            reservation_rows = conn.execute(
                """
                SELECT DISTINCT sra.reservationId
                FROM stay_room_assignment sra
                JOIN stay_room_guest srg ON srg.stayAssignmentId = sra.stayAssignmentId
                WHERE srg.guestId = ?
                ORDER BY sra.reservationId
                """,
                (selected_guest_id,),
            ).fetchall()

            room_rows = conn.execute(
                """
                SELECT DISTINCT r.roomNum
                FROM stay_room_assignment sra
                JOIN stay_room_guest srg ON srg.stayAssignmentId = sra.stayAssignmentId
                JOIN room r ON r.roomId = sra.roomId
                WHERE srg.guestId = ?
                  AND sra.assignedStartDate <= ?
                  AND COALESCE(sra.assignedEndDate, '9999-12-31') > ?
                  AND sra.assignmentStatus = 'OCCUPIED'
                ORDER BY r.roomNum
                """,
                (selected_guest_id, current_date, current_date),
            ).fetchall()

            selected_guest_profile = dict(profile_row)
            selected_guest_profile["reservationIds"] = ", ".join(
                str(row["reservationId"]) for row in reservation_rows
            ) or "No linked reservation"
            selected_guest_profile["assignedRooms"] = ", ".join(
                row["roomNum"] for row in room_rows
            ) or "No active room"

            if selected_guest_contact is not None:
                selected_guest_profile["lastKnownLocation"] = selected_guest_contact["lastKnownLocation"]
                selected_guest_profile["messageContent"] = selected_guest_contact["messageContent"]
            else:
                selected_guest_profile["lastKnownLocation"] = "No recent swipe recorded"
                selected_guest_profile["messageContent"] = "No recent guest message"

            selected_guest_messages = load_guest_messages(conn, selected_guest_id)
            selected_guest_can_delete = get_guest_delete_blocker(conn, selected_guest_id) is None

    selected_guest_services = []
    if selected_guest_id is not None:
        selected_guest_services = conn.execute(
            """
            SELECT
                chargeType,
                COUNT(*) AS serviceCount,
                ROUND(SUM(amount), 2) AS totalAmount,
                MAX(chargeTime) AS lastUsedAt
            FROM charge
            WHERE usedByGuestId = ?
            GROUP BY chargeType
            ORDER BY totalAmount DESC, chargeType
            """,
            (selected_guest_id,),
        ).fetchall()

    conn.close()

    return render_template(
        "guests.html",
        guestContacts=guest_contacts,
        selectedGuestProfile=selected_guest_profile,
        selectedGuestServices=selected_guest_services,
        selectedGuestMessages=selected_guest_messages,
        selectedGuestCanDelete=selected_guest_can_delete,
        selectedGuestId=selected_guest_id,
        searchText=search_text,
        snapshotDate=current_date,
        pageMessage=page_message,
        pageMessageType=page_message_type,
        pageTitle="Guests",
    )


@app.route("/guests/create", methods=["POST"])
def create_guest():
    first_name = clean_text(request.form.get("firstName"))
    last_name = clean_text(request.form.get("lastName"))
    email_address = optional_text(request.form.get("emailAddress"))
    phone_number = optional_text(request.form.get("phoneNumber"))
    pin_code = clean_text(request.form.get("pinCode"))
    is_confidential = parse_checkbox(request.form.get("isConfidential"))

    if not first_name or not last_name or not pin_code:
        return redirect_with_message(
            "guests_page",
            "First name, last name, and PIN are required.",
            "error",
        )

    conn = get_db_connection()
    try:
        person_id = get_next_id(conn, "person", "personId")
        guest_id = get_next_id(conn, "guest", "guestId")
        party_id = get_next_id(conn, "party", "partyId")

        conn.execute(
            """
            INSERT INTO person (personId, firstName, lastName, emailAddress, phoneNumber)
            VALUES (?, ?, ?, ?, ?)
            """,
            (person_id, first_name, last_name, email_address, phone_number),
        )
        conn.execute(
            """
            INSERT INTO guest (guestId, personId, pinCode, isConfidential)
            VALUES (?, ?, ?, ?)
            """,
            (guest_id, person_id, pin_code, is_confidential),
        )
        conn.execute(
            """
            INSERT INTO party (partyId, partyType, personId, organizationId, authorizedRepPersonId)
            VALUES (?, 'PERSON', ?, NULL, NULL)
            """,
            (party_id, person_id),
        )
        conn.commit()
    except sqlite3.Error:
        conn.rollback()
        conn.close()
        return redirect_with_message(
            "guests_page",
            "Guest could not be added.",
            "error",
        )

    conn.close()
    return redirect_with_message(
        "guests_page",
        "Guest added.",
        guestId=guest_id,
    )


@app.route("/guests/update", methods=["POST"])
def update_guest():
    guest_id = parse_optional_int(request.form.get("guestId"))
    search_text = clean_text(request.form.get("search"))
    first_name = clean_text(request.form.get("firstName"))
    last_name = clean_text(request.form.get("lastName"))
    email_address = optional_text(request.form.get("emailAddress"))
    phone_number = optional_text(request.form.get("phoneNumber"))
    pin_code = clean_text(request.form.get("pinCode"))
    is_confidential = parse_checkbox(request.form.get("isConfidential"))

    if guest_id is None:
        return redirect_with_message(
            "guests_page",
            "Choose a guest before updating.",
            "error",
            search=search_text,
        )

    if not first_name or not last_name or not pin_code:
        return redirect_with_message(
            "guests_page",
            "First name, last name, and PIN are required.",
            "error",
            guestId=guest_id,
            search=search_text,
        )

    conn = get_db_connection()
    guest_row = conn.execute(
        "SELECT personId FROM guest WHERE guestId = ?",
        (guest_id,),
    ).fetchone()

    if guest_row is None:
        conn.close()
        return redirect_with_message(
            "guests_page",
            "Guest record was not found.",
            "error",
            search=search_text,
        )

    try:
        conn.execute(
            """
            UPDATE person
            SET firstName = ?, lastName = ?, emailAddress = ?, phoneNumber = ?
            WHERE personId = ?
            """,
            (first_name, last_name, email_address, phone_number, guest_row["personId"]),
        )
        conn.execute(
            """
            UPDATE guest
            SET pinCode = ?, isConfidential = ?
            WHERE guestId = ?
            """,
            (pin_code, is_confidential, guest_id),
        )
        conn.commit()
    except sqlite3.Error:
        conn.rollback()
        conn.close()
        return redirect_with_message(
            "guests_page",
            "Guest update failed.",
            "error",
            guestId=guest_id,
            search=search_text,
        )

    conn.close()
    return redirect_with_message(
        "guests_page",
        "Guest updated.",
        guestId=guest_id,
        search=search_text,
    )


@app.route("/guests/delete", methods=["POST"])
def delete_guest():
    guest_id = parse_optional_int(request.form.get("guestId"))
    search_text = clean_text(request.form.get("search"))

    if guest_id is None:
        return redirect_with_message(
            "guests_page",
            "Choose a guest before deleting.",
            "error",
            search=search_text,
        )

    conn = get_db_connection()
    blocker_message = get_guest_delete_blocker(conn, guest_id)
    if blocker_message is not None:
        conn.close()
        return redirect_with_message(
            "guests_page",
            blocker_message,
            "error",
            guestId=guest_id,
            search=search_text,
        )

    guest_row = conn.execute(
        """
        SELECT g.personId, p.partyId
        FROM guest g
        LEFT JOIN party p ON p.personId = g.personId AND p.partyType = 'PERSON'
        WHERE g.guestId = ?
        """,
        (guest_id,),
    ).fetchone()

    if guest_row is None:
        conn.close()
        return redirect_with_message(
            "guests_page",
            "Guest record was not found.",
            "error",
            search=search_text,
        )

    try:
        if guest_row["partyId"] is not None:
            conn.execute("DELETE FROM party WHERE partyId = ?", (guest_row["partyId"],))
        conn.execute("DELETE FROM guest WHERE guestId = ?", (guest_id,))
        conn.execute("DELETE FROM person WHERE personId = ?", (guest_row["personId"],))
        conn.commit()
    except sqlite3.Error:
        conn.rollback()
        conn.close()
        return redirect_with_message(
            "guests_page",
            "Guest could not be deleted.",
            "error",
            guestId=guest_id,
            search=search_text,
        )

    conn.close()
    return redirect_with_message(
        "guests_page",
        "Guest deleted.",
        search=search_text,
    )


@app.route("/guests/message/create", methods=["POST"])
def create_guest_message():
    guest_id = parse_optional_int(request.form.get("guestId"))
    search_text = clean_text(request.form.get("search"))
    message_content = clean_text(request.form.get("messageContent"))

    if guest_id is None or not message_content:
        return redirect_with_message(
            "guests_page",
            "Choose a guest and enter a message.",
            "error",
            guestId=guest_id,
            search=search_text,
        )

    conn = get_db_connection()
    try:
        message_id = get_next_id(conn, "guest_message", "messageId")
        conn.execute(
            """
            INSERT INTO guest_message (messageId, guestId, messageContent, messageTime)
            VALUES (?, ?, ?, ?)
            """,
            (message_id, guest_id, message_content, get_current_timestamp()),
        )
        conn.commit()
    except sqlite3.Error:
        conn.rollback()
        conn.close()
        return redirect_with_message(
            "guests_page",
            "Guest message could not be added.",
            "error",
            guestId=guest_id,
            search=search_text,
        )

    conn.close()
    return redirect_with_message(
        "guests_page",
        "Guest message added.",
        guestId=guest_id,
        search=search_text,
    )


@app.route("/guests/message/delete", methods=["POST"])
def delete_guest_message():
    guest_id = parse_optional_int(request.form.get("guestId"))
    message_id = parse_optional_int(request.form.get("messageId"))
    search_text = clean_text(request.form.get("search"))

    if guest_id is None or message_id is None:
        return redirect_with_message(
            "guests_page",
            "Choose a message before deleting.",
            "error",
            guestId=guest_id,
            search=search_text,
        )

    conn = get_db_connection()
    conn.execute(
        "DELETE FROM guest_message WHERE messageId = ? AND guestId = ?",
        (message_id, guest_id),
    )
    conn.commit()
    conn.close()

    return redirect_with_message(
        "guests_page",
        "Guest message deleted.",
        guestId=guest_id,
        search=search_text,
    )


@app.route("/operations/event/create", methods=["POST"])
def create_event():
    event_name = clean_text(request.form.get("eventName"))
    host_party_id = parse_optional_int(request.form.get("hostPartyId"))
    billed_party_id = parse_optional_int(request.form.get("billedPartyId"))
    start_date = clean_text(request.form.get("startDate"))
    end_date = clean_text(request.form.get("endDate"))

    try:
        estimated_attendance = parse_optional_int(request.form.get("estimatedAttendance"))
        estimated_guest_count = parse_optional_int(request.form.get("estimatedGuestCount"))
    except ValueError:
        return redirect_with_message(
            "operations_page",
            "Estimated counts must be whole numbers.",
            "error",
        )

    if not event_name or billed_party_id is None or not start_date or not end_date:
        return redirect_with_message(
            "operations_page",
            "Event name, billed party, start date, and end date are required.",
            "error",
        )

    if end_date < start_date:
        return redirect_with_message(
            "operations_page",
            "Event end date must be on or after the start date.",
            "error",
        )

    conn = get_db_connection()
    try:
        event_id = get_next_id(conn, "event", "eventId")
        conn.execute(
            """
            INSERT INTO event (
                eventId, eventName, hostPartyId, billedPartyId,
                startDate, endDate, estimatedAttendance, estimatedGuestCount
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                event_id,
                event_name,
                host_party_id,
                billed_party_id,
                start_date,
                end_date,
                estimated_attendance,
                estimated_guest_count,
            ),
        )
        conn.commit()
    except sqlite3.Error:
        conn.rollback()
        conn.close()
        return redirect_with_message(
            "operations_page",
            "Event could not be added.",
            "error",
        )

    conn.close()
    return redirect_with_message(
        "operations_page",
        "Event added.",
        eventId=event_id,
    )


@app.route("/operations/event/update", methods=["POST"])
def update_event():
    event_id = parse_optional_int(request.form.get("eventId"))
    event_name = clean_text(request.form.get("eventName"))
    host_party_id = parse_optional_int(request.form.get("hostPartyId"))
    billed_party_id = parse_optional_int(request.form.get("billedPartyId"))
    start_date = clean_text(request.form.get("startDate"))
    end_date = clean_text(request.form.get("endDate"))

    try:
        estimated_attendance = parse_optional_int(request.form.get("estimatedAttendance"))
        estimated_guest_count = parse_optional_int(request.form.get("estimatedGuestCount"))
    except ValueError:
        return redirect_with_message(
            "operations_page",
            "Estimated counts must be whole numbers.",
            "error",
            eventId=event_id,
        )

    if event_id is None:
        return redirect_with_message(
            "operations_page",
            "Choose an event before updating.",
            "error",
        )

    if not event_name or billed_party_id is None or not start_date or not end_date:
        return redirect_with_message(
            "operations_page",
            "Event name, billed party, start date, and end date are required.",
            "error",
            eventId=event_id,
        )

    if end_date < start_date:
        return redirect_with_message(
            "operations_page",
            "Event end date must be on or after the start date.",
            "error",
            eventId=event_id,
        )

    conn = get_db_connection()
    try:
        conn.execute(
            """
            UPDATE event
            SET eventName = ?, hostPartyId = ?, billedPartyId = ?,
                startDate = ?, endDate = ?, estimatedAttendance = ?, estimatedGuestCount = ?
            WHERE eventId = ?
            """,
            (
                event_name,
                host_party_id,
                billed_party_id,
                start_date,
                end_date,
                estimated_attendance,
                estimated_guest_count,
                event_id,
            ),
        )
        conn.commit()
    except sqlite3.Error:
        conn.rollback()
        conn.close()
        return redirect_with_message(
            "operations_page",
            "Event update failed.",
            "error",
            eventId=event_id,
        )

    conn.close()
    return redirect_with_message(
        "operations_page",
        "Event updated.",
        eventId=event_id,
    )


@app.route("/operations/event/delete", methods=["POST"])
def delete_event():
    event_id = parse_optional_int(request.form.get("eventId"))

    if event_id is None:
        return redirect_with_message(
            "operations_page",
            "Choose an event before deleting.",
            "error",
        )

    conn = get_db_connection()
    blocker_message = get_event_delete_blocker(conn, event_id)
    if blocker_message is not None:
        conn.close()
        return redirect_with_message(
            "operations_page",
            blocker_message,
            "error",
            eventId=event_id,
        )

    try:
        conn.execute("DELETE FROM event_guest WHERE eventId = ?", (event_id,))
        conn.execute("DELETE FROM event_room_usage WHERE eventId = ?", (event_id,))
        conn.execute("DELETE FROM event_organization WHERE eventId = ?", (event_id,))
        conn.execute("DELETE FROM event WHERE eventId = ?", (event_id,))
        conn.commit()
    except sqlite3.Error:
        conn.rollback()
        conn.close()
        return redirect_with_message(
            "operations_page",
            "Event could not be deleted.",
            "error",
            eventId=event_id,
        )

    conn.close()
    return redirect_with_message(
        "operations_page",
        "Event deleted.",
    )


@app.route("/operations/event-room/create", methods=["POST"])
def create_event_room_usage():
    event_id = parse_optional_int(request.form.get("eventId"))
    room_id = parse_optional_int(request.form.get("roomId"))
    usage_date = clean_text(request.form.get("usageDate"))
    usage_slot = clean_text(request.form.get("usageSlot"))
    is_eating_usage = parse_checkbox(request.form.get("isEatingUsage"))

    if event_id is None or room_id is None or not usage_date or usage_slot not in USAGE_SLOT_TYPES:
        return redirect_with_message(
            "operations_page",
            "Choose an event, room, usage date, and usage slot.",
            "error",
            eventId=event_id,
        )

    conn = get_db_connection()
    event_row = conn.execute(
        "SELECT startDate, endDate FROM event WHERE eventId = ?",
        (event_id,),
    ).fetchone()
    if event_row is None:
        conn.close()
        return redirect_with_message(
            "operations_page",
            "Selected event was not found.",
            "error",
            eventId=event_id,
        )

    if usage_date < event_row["startDate"] or usage_date > event_row["endDate"]:
        conn.close()
        return redirect_with_message(
            "operations_page",
            "Room usage date must stay inside the event date range.",
            "error",
            eventId=event_id,
        )

    room_row = conn.execute(
        """
        SELECT 1
        FROM room_capability rc
        JOIN capability_type ct ON ct.capabilityTypeId = rc.capabilityTypeId
        WHERE rc.roomId = ?
          AND ct.capabilityCode IN ('MEETING', 'SUITE')
        LIMIT 1
        """,
        (room_id,),
    ).fetchone()
    if room_row is None:
        conn.close()
        return redirect_with_message(
            "operations_page",
            "That room cannot be assigned to an event.",
            "error",
            eventId=event_id,
        )

    try:
        usage_id = get_next_id(conn, "event_room_usage", "usageId")
        conn.execute(
            """
            INSERT INTO event_room_usage (
                usageId, eventId, roomId, usageDate, usageSlot, isEatingUsage
            ) VALUES (?, ?, ?, ?, ?, ?)
            """,
            (usage_id, event_id, room_id, usage_date, usage_slot, is_eating_usage),
        )
        conn.commit()
    except sqlite3.Error:
        conn.rollback()
        conn.close()
        return redirect_with_message(
            "operations_page",
            "Room usage could not be added. Check for room and time conflicts.",
            "error",
            eventId=event_id,
        )

    conn.close()
    return redirect_with_message(
        "operations_page",
        "Event room usage added.",
        eventId=event_id,
    )


@app.route("/operations/event-room/delete", methods=["POST"])
def delete_event_room_usage():
    event_id = parse_optional_int(request.form.get("eventId"))
    usage_id = parse_optional_int(request.form.get("usageId"))

    if event_id is None or usage_id is None:
        return redirect_with_message(
            "operations_page",
            "Choose a room usage record before deleting.",
            "error",
            eventId=event_id,
        )

    conn = get_db_connection()
    conn.execute(
        "DELETE FROM event_room_usage WHERE usageId = ? AND eventId = ?",
        (usage_id, event_id),
    )
    conn.commit()
    conn.close()

    return redirect_with_message(
        "operations_page",
        "Event room usage deleted.",
        eventId=event_id,
    )


@app.route("/operations/event-guest/create", methods=["POST"])
def create_event_guest():
    event_id = parse_optional_int(request.form.get("eventId"))
    guest_id = parse_optional_int(request.form.get("guestId"))
    role_name = optional_text(request.form.get("roleName"))

    if event_id is None or guest_id is None:
        return redirect_with_message(
            "operations_page",
            "Choose an event and guest before adding an attendee.",
            "error",
            eventId=event_id,
        )

    conn = get_db_connection()
    try:
        conn.execute(
            """
            INSERT INTO event_guest (eventId, guestId, roleName)
            VALUES (?, ?, ?)
            """,
            (event_id, guest_id, role_name),
        )
        conn.commit()
    except sqlite3.Error:
        conn.rollback()
        conn.close()
        return redirect_with_message(
            "operations_page",
            "Event guest link could not be added.",
            "error",
            eventId=event_id,
        )

    conn.close()
    return redirect_with_message(
        "operations_page",
        "Event guest added.",
        eventId=event_id,
    )


@app.route("/operations/event-guest/delete", methods=["POST"])
def delete_event_guest():
    event_id = parse_optional_int(request.form.get("eventId"))
    guest_id = parse_optional_int(request.form.get("guestId"))

    if event_id is None or guest_id is None:
        return redirect_with_message(
            "operations_page",
            "Choose an event guest link before deleting.",
            "error",
            eventId=event_id,
        )

    conn = get_db_connection()
    conn.execute(
        "DELETE FROM event_guest WHERE eventId = ? AND guestId = ?",
        (event_id, guest_id),
    )
    conn.commit()
    conn.close()

    return redirect_with_message(
        "operations_page",
        "Event guest deleted.",
        eventId=event_id,
    )


@app.route("/rooms/status/create", methods=["POST"])
def create_room_status():
    start_date = clean_text(request.form.get("startDate"))
    end_date = clean_text(request.form.get("endDate"))
    status_date = clean_text(request.form.get("statusDate"))
    room_id = parse_optional_int(request.form.get("roomId"))
    status_type = normalize_room_status(clean_text(request.form.get("statusType")))
    employee_id = parse_optional_int(request.form.get("employeeId"))
    notes = optional_text(request.form.get("notes"))
    start_time = parse_date_input(request.form.get("startTime"))
    end_time = parse_date_input(request.form.get("endTime"))

    if room_id is None or not status_type or start_time is None or end_time is None:
        return redirect_with_message(
            "rooms_page",
            "Room, status type, start date, and end date are required.",
            "error",
            start=start_date,
            end=end_date,
            status=status_date,
        )

    if status_type not in ROOM_STATUS_TYPES:
        return redirect_with_message(
            "rooms_page",
            "Choose a valid room status type.",
            "error",
            start=start_date,
            end=end_date,
            status=status_date,
        )

    if end_time < start_time:
        return redirect_with_message(
            "rooms_page",
            "Status end date must be on or after the start date.",
            "error",
            start=start_date,
            end=end_date,
            status=status_date,
        )

    conn = get_db_connection()
    try:
        status_id = get_next_id(conn, "room_status", "statusId")
        conn.execute(
            """
            INSERT INTO room_status (
                statusId, roomId, statusType, startTime, endTime, employeeId, notes
            ) VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (status_id, room_id, status_type, start_time, end_time, employee_id, notes),
        )
        conn.commit()
    except sqlite3.Error:
        conn.rollback()
        conn.close()
        return redirect_with_message(
            "rooms_page",
            "Room status could not be added.",
            "error",
            start=start_date,
            end=end_date,
            status=status_date,
        )

    conn.close()
    return redirect_with_message(
        "rooms_page",
        "Room status added.",
        start=start_date,
        end=end_date,
        status=status_date,
        statusId=status_id,
    )


@app.route("/rooms/status/update", methods=["POST"])
def update_room_status():
    start_date = clean_text(request.form.get("startDate"))
    end_date = clean_text(request.form.get("endDate"))
    status_date = clean_text(request.form.get("statusDate"))
    status_id = parse_optional_int(request.form.get("statusId"))
    room_id = parse_optional_int(request.form.get("roomId"))
    status_type = normalize_room_status(clean_text(request.form.get("statusType")))
    employee_id = parse_optional_int(request.form.get("employeeId"))
    notes = optional_text(request.form.get("notes"))
    start_time = parse_date_input(request.form.get("startTime"))
    end_time = parse_date_input(request.form.get("endTime"))

    if status_id is None or room_id is None or not status_type or start_time is None or end_time is None:
        return redirect_with_message(
            "rooms_page",
            "Choose a status record and fill in the required fields.",
            "error",
            start=start_date,
            end=end_date,
            status=status_date,
            statusId=status_id,
        )

    if status_type not in ROOM_STATUS_TYPES:
        return redirect_with_message(
            "rooms_page",
            "Choose a valid room status type.",
            "error",
            start=start_date,
            end=end_date,
            status=status_date,
            statusId=status_id,
        )

    if end_time < start_time:
        return redirect_with_message(
            "rooms_page",
            "Status end date must be on or after the start date.",
            "error",
            start=start_date,
            end=end_date,
            status=status_date,
            statusId=status_id,
        )

    conn = get_db_connection()
    try:
        conn.execute(
            """
            UPDATE room_status
            SET roomId = ?, statusType = ?, startTime = ?, endTime = ?, employeeId = ?, notes = ?
            WHERE statusId = ?
            """,
            (room_id, status_type, start_time, end_time, employee_id, notes, status_id),
        )
        conn.commit()
    except sqlite3.Error:
        conn.rollback()
        conn.close()
        return redirect_with_message(
            "rooms_page",
            "Room status update failed.",
            "error",
            start=start_date,
            end=end_date,
            status=status_date,
            statusId=status_id,
        )

    conn.close()
    return redirect_with_message(
        "rooms_page",
        "Room status updated.",
        start=start_date,
        end=end_date,
        status=status_date,
        statusId=status_id,
    )


@app.route("/rooms/status/delete", methods=["POST"])
def delete_room_status():
    start_date = clean_text(request.form.get("startDate"))
    end_date = clean_text(request.form.get("endDate"))
    status_date = clean_text(request.form.get("statusDate"))
    status_id = parse_optional_int(request.form.get("statusId"))

    if status_id is None:
        return redirect_with_message(
            "rooms_page",
            "Choose a status record before deleting.",
            "error",
            start=start_date,
            end=end_date,
            status=status_date,
        )

    conn = get_db_connection()
    conn.execute("DELETE FROM room_status WHERE statusId = ?", (status_id,))
    conn.commit()
    conn.close()

    return redirect_with_message(
        "rooms_page",
        "Room status deleted.",
        start=start_date,
        end=end_date,
        status=status_date,
    )


@app.route("/reservations/create", methods=["POST"])
def create_reservation():
    booked_by_party_id = parse_optional_int(request.form.get("bookedByPartyId"))
    billing_party_id = parse_optional_int(request.form.get("billingPartyId"))
    booking_date = clean_text(request.form.get("bookingDate"))
    check_in_date = clean_text(request.form.get("plannedCheckInDate"))
    check_out_date = clean_text(request.form.get("plannedCheckOutDate"))
    reservation_status = clean_text(request.form.get("reservationStatus"))
    search_text = clean_text(request.form.get("search"))

    try:
        advance_deposit = parse_optional_float(request.form.get("advanceDeposit"))
    except ValueError:
        return redirect_with_message(
            "reservations_page",
            "Advance deposit must be a number.",
            "error",
            search=search_text,
        )

    if advance_deposit is None:
        advance_deposit = 0

    if (
        booked_by_party_id is None
        or billing_party_id is None
        or not booking_date
        or not check_in_date
        or not check_out_date
        or reservation_status not in RESERVATION_STATUS_TYPES
    ):
        return redirect_with_message(
            "reservations_page",
            "Fill in all required reservation fields.",
            "error",
            search=search_text,
        )

    if check_out_date <= check_in_date:
        return redirect_with_message(
            "reservations_page",
            "Check-out date must be after check-in date.",
            "error",
            search=search_text,
        )

    if advance_deposit < 0:
        return redirect_with_message(
            "reservations_page",
            "Advance deposit cannot be negative.",
            "error",
            search=search_text,
        )

    conn = get_db_connection()
    try:
        reservation_id = get_next_id(conn, "reservation", "reservationId")
        conn.execute(
            """
            INSERT INTO reservation (
                reservationId, bookedByPartyId, billingPartyId, bookingDate,
                plannedCheckInDate, plannedCheckOutDate, reservationStatus, advanceDeposit
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                reservation_id,
                booked_by_party_id,
                billing_party_id,
                booking_date,
                check_in_date,
                check_out_date,
                reservation_status,
                advance_deposit,
            ),
        )
        conn.commit()
    except sqlite3.Error:
        conn.rollback()
        conn.close()
        return redirect_with_message(
            "reservations_page",
            "Reservation could not be added.",
            "error",
            search=search_text,
        )

    conn.close()
    return redirect_with_message(
        "reservations_page",
        "Reservation added.",
        reservationId=reservation_id,
        search=search_text,
    )


@app.route("/reservations/update", methods=["POST"])
def update_reservation():
    reservation_id = parse_optional_int(request.form.get("reservationId"))
    booked_by_party_id = parse_optional_int(request.form.get("bookedByPartyId"))
    billing_party_id = parse_optional_int(request.form.get("billingPartyId"))
    booking_date = clean_text(request.form.get("bookingDate"))
    check_in_date = clean_text(request.form.get("plannedCheckInDate"))
    check_out_date = clean_text(request.form.get("plannedCheckOutDate"))
    reservation_status = clean_text(request.form.get("reservationStatus"))
    search_text = clean_text(request.form.get("search"))

    try:
        advance_deposit = parse_optional_float(request.form.get("advanceDeposit"))
    except ValueError:
        return redirect_with_message(
            "reservations_page",
            "Advance deposit must be a number.",
            "error",
            reservationId=reservation_id,
            search=search_text,
        )

    if advance_deposit is None:
        advance_deposit = 0

    if reservation_id is None:
        return redirect_with_message(
            "reservations_page",
            "Choose a reservation before updating.",
            "error",
            search=search_text,
        )

    if (
        booked_by_party_id is None
        or billing_party_id is None
        or not booking_date
        or not check_in_date
        or not check_out_date
        or reservation_status not in RESERVATION_STATUS_TYPES
    ):
        return redirect_with_message(
            "reservations_page",
            "Fill in all required reservation fields.",
            "error",
            reservationId=reservation_id,
            search=search_text,
        )

    if check_out_date <= check_in_date:
        return redirect_with_message(
            "reservations_page",
            "Check-out date must be after check-in date.",
            "error",
            reservationId=reservation_id,
            search=search_text,
        )

    if advance_deposit < 0:
        return redirect_with_message(
            "reservations_page",
            "Advance deposit cannot be negative.",
            "error",
            reservationId=reservation_id,
            search=search_text,
        )

    conn = get_db_connection()
    try:
        conn.execute(
            """
            UPDATE reservation
            SET bookedByPartyId = ?, billingPartyId = ?, bookingDate = ?,
                plannedCheckInDate = ?, plannedCheckOutDate = ?,
                reservationStatus = ?, advanceDeposit = ?
            WHERE reservationId = ?
            """,
            (
                booked_by_party_id,
                billing_party_id,
                booking_date,
                check_in_date,
                check_out_date,
                reservation_status,
                advance_deposit,
                reservation_id,
            ),
        )
        conn.commit()
    except sqlite3.Error:
        conn.rollback()
        conn.close()
        return redirect_with_message(
            "reservations_page",
            "Reservation update failed.",
            "error",
            reservationId=reservation_id,
            search=search_text,
        )

    conn.close()
    return redirect_with_message(
        "reservations_page",
        "Reservation updated.",
        reservationId=reservation_id,
        search=search_text,
    )


@app.route("/reservations/delete", methods=["POST"])
def delete_reservation():
    reservation_id = parse_optional_int(request.form.get("reservationId"))
    search_text = clean_text(request.form.get("search"))

    if reservation_id is None:
        return redirect_with_message(
            "reservations_page",
            "Choose a reservation before deleting.",
            "error",
            search=search_text,
        )

    conn = get_db_connection()
    blocker_message = get_reservation_delete_blocker(conn, reservation_id)
    if blocker_message is not None:
        conn.close()
        return redirect_with_message(
            "reservations_page",
            blocker_message,
            "error",
            reservationId=reservation_id,
            search=search_text,
        )

    try:
        preference_row = conn.execute(
            "SELECT preferenceId FROM reservation_preference WHERE reservationId = ?",
            (reservation_id,),
        ).fetchone()
        if preference_row is not None:
            conn.execute(
                "DELETE FROM reservation_bed_preference WHERE preferenceId = ?",
                (preference_row["preferenceId"],),
            )
            conn.execute(
                "DELETE FROM reservation_preference WHERE preferenceId = ?",
                (preference_row["preferenceId"],),
            )
        conn.execute("DELETE FROM reservation WHERE reservationId = ?", (reservation_id,))
        conn.commit()
    except sqlite3.Error:
        conn.rollback()
        conn.close()
        return redirect_with_message(
            "reservations_page",
            "Reservation could not be deleted.",
            "error",
            reservationId=reservation_id,
            search=search_text,
        )

    conn.close()
    return redirect_with_message(
        "reservations_page",
        "Reservation deleted.",
        search=search_text,
    )


@app.route("/reservations/assignment/create", methods=["POST"])
def create_stay_assignment():
    reservation_id = parse_optional_int(request.form.get("reservationId"))
    room_id = parse_optional_int(request.form.get("roomId"))
    assigned_start = clean_text(request.form.get("assignedStartDate"))
    assigned_end = clean_text(request.form.get("assignedEndDate"))
    assignment_status = clean_text(request.form.get("assignmentStatus"))
    search_text = clean_text(request.form.get("search"))

    if (
        reservation_id is None
        or room_id is None
        or not assigned_start
        or assignment_status not in ASSIGNMENT_STATUS_TYPES
    ):
        return redirect_with_message(
            "reservations_page",
            "Choose a reservation, room, start date, and assignment status.",
            "error",
            reservationId=reservation_id,
            search=search_text,
        )

    if assigned_end and assigned_end <= assigned_start:
        return redirect_with_message(
            "reservations_page",
            "Assignment end date must be after the start date.",
            "error",
            reservationId=reservation_id,
            search=search_text,
        )

    conn = get_db_connection()
    reservation_row = conn.execute(
        """
        SELECT plannedCheckInDate, plannedCheckOutDate
        FROM reservation
        WHERE reservationId = ?
        """,
        (reservation_id,),
    ).fetchone()
    if reservation_row is None:
        conn.close()
        return redirect_with_message(
            "reservations_page",
            "Selected reservation was not found.",
            "error",
            search=search_text,
        )

    if assigned_start < reservation_row["plannedCheckInDate"]:
        conn.close()
        return redirect_with_message(
            "reservations_page",
            "Assignment start date cannot be before the reservation check-in date.",
            "error",
            reservationId=reservation_id,
            search=search_text,
        )

    if assigned_end and assigned_end > reservation_row["plannedCheckOutDate"]:
        conn.close()
        return redirect_with_message(
            "reservations_page",
            "Assignment end date cannot be after the reservation check-out date.",
            "error",
            reservationId=reservation_id,
            search=search_text,
        )

    room_ok = conn.execute(
        """
        SELECT 1
        FROM room_capability rc
        JOIN capability_type ct ON ct.capabilityTypeId = rc.capabilityTypeId
        WHERE rc.roomId = ?
          AND ct.capabilityCode IN ('SLEEPING', 'SUITE')
        LIMIT 1
        """,
        (room_id,),
    ).fetchone()
    if room_ok is None:
        conn.close()
        return redirect_with_message(
            "reservations_page",
            "That room cannot be assigned for a stay.",
            "error",
            reservationId=reservation_id,
            search=search_text,
        )

    conflict_assignment_id = find_room_assignment_conflict(
        conn,
        room_id,
        assigned_start,
        assigned_end,
    )
    if conflict_assignment_id is not None:
        conn.close()
        return redirect_with_message(
            "reservations_page",
            "That room is already assigned during the selected dates.",
            "error",
            reservationId=reservation_id,
            search=search_text,
        )

    try:
        assignment_id = get_next_id(conn, "stay_room_assignment", "stayAssignmentId")
        conn.execute(
            """
            INSERT INTO stay_room_assignment (
                stayAssignmentId, reservationId, roomId,
                assignedStartDate, assignedEndDate, assignmentStatus
            ) VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                assignment_id,
                reservation_id,
                room_id,
                assigned_start,
                assigned_end or None,
                assignment_status,
            ),
        )
        conn.commit()
    except sqlite3.Error:
        conn.rollback()
        conn.close()
        return redirect_with_message(
            "reservations_page",
            "Room assignment could not be added.",
            "error",
            reservationId=reservation_id,
            search=search_text,
        )

    conn.close()
    return redirect_with_message(
        "reservations_page",
        "Room assignment added.",
        reservationId=reservation_id,
        assignmentId=assignment_id,
        search=search_text,
    )


@app.route("/reservations/assignment/update", methods=["POST"])
def update_stay_assignment():
    reservation_id = parse_optional_int(request.form.get("reservationId"))
    assignment_id = parse_optional_int(request.form.get("stayAssignmentId"))
    room_id = parse_optional_int(request.form.get("roomId"))
    assigned_start = clean_text(request.form.get("assignedStartDate"))
    assigned_end = clean_text(request.form.get("assignedEndDate"))
    assignment_status = clean_text(request.form.get("assignmentStatus"))
    search_text = clean_text(request.form.get("search"))

    if (
        reservation_id is None
        or assignment_id is None
        or room_id is None
        or not assigned_start
        or assignment_status not in ASSIGNMENT_STATUS_TYPES
    ):
        return redirect_with_message(
            "reservations_page",
            "Choose an assignment and fill in the required fields.",
            "error",
            reservationId=reservation_id,
            assignmentId=assignment_id,
            search=search_text,
        )

    if assigned_end and assigned_end <= assigned_start:
        return redirect_with_message(
            "reservations_page",
            "Assignment end date must be after the start date.",
            "error",
            reservationId=reservation_id,
            assignmentId=assignment_id,
            search=search_text,
        )

    conn = get_db_connection()
    reservation_row = conn.execute(
        """
        SELECT plannedCheckInDate, plannedCheckOutDate
        FROM reservation
        WHERE reservationId = ?
        """,
        (reservation_id,),
    ).fetchone()
    if reservation_row is None:
        conn.close()
        return redirect_with_message(
            "reservations_page",
            "Selected reservation was not found.",
            "error",
            search=search_text,
        )

    if assigned_start < reservation_row["plannedCheckInDate"]:
        conn.close()
        return redirect_with_message(
            "reservations_page",
            "Assignment start date cannot be before the reservation check-in date.",
            "error",
            reservationId=reservation_id,
            assignmentId=assignment_id,
            search=search_text,
        )

    if assigned_end and assigned_end > reservation_row["plannedCheckOutDate"]:
        conn.close()
        return redirect_with_message(
            "reservations_page",
            "Assignment end date cannot be after the reservation check-out date.",
            "error",
            reservationId=reservation_id,
            assignmentId=assignment_id,
            search=search_text,
        )

    room_ok = conn.execute(
        """
        SELECT 1
        FROM room_capability rc
        JOIN capability_type ct ON ct.capabilityTypeId = rc.capabilityTypeId
        WHERE rc.roomId = ?
          AND ct.capabilityCode IN ('SLEEPING', 'SUITE')
        LIMIT 1
        """,
        (room_id,),
    ).fetchone()
    if room_ok is None:
        conn.close()
        return redirect_with_message(
            "reservations_page",
            "That room cannot be assigned for a stay.",
            "error",
            reservationId=reservation_id,
            assignmentId=assignment_id,
            search=search_text,
        )

    conflict_assignment_id = find_room_assignment_conflict(
        conn,
        room_id,
        assigned_start,
        assigned_end,
        assignment_id,
    )
    if conflict_assignment_id is not None:
        conn.close()
        return redirect_with_message(
            "reservations_page",
            "That room is already assigned during the selected dates.",
            "error",
            reservationId=reservation_id,
            assignmentId=assignment_id,
            search=search_text,
        )

    try:
        conn.execute(
            """
            UPDATE stay_room_assignment
            SET roomId = ?, assignedStartDate = ?, assignedEndDate = ?, assignmentStatus = ?
            WHERE stayAssignmentId = ?
            """,
            (
                room_id,
                assigned_start,
                assigned_end or None,
                assignment_status,
                assignment_id,
            ),
        )
        conn.commit()
    except sqlite3.Error:
        conn.rollback()
        conn.close()
        return redirect_with_message(
            "reservations_page",
            "Room assignment update failed.",
            "error",
            reservationId=reservation_id,
            assignmentId=assignment_id,
            search=search_text,
        )

    conn.close()
    return redirect_with_message(
        "reservations_page",
        "Room assignment updated.",
        reservationId=reservation_id,
        assignmentId=assignment_id,
        search=search_text,
    )


@app.route("/reservations/assignment/delete", methods=["POST"])
def delete_stay_assignment():
    reservation_id = parse_optional_int(request.form.get("reservationId"))
    assignment_id = parse_optional_int(request.form.get("stayAssignmentId"))
    search_text = clean_text(request.form.get("search"))

    if reservation_id is None or assignment_id is None:
        return redirect_with_message(
            "reservations_page",
            "Choose an assignment before deleting.",
            "error",
            reservationId=reservation_id,
            search=search_text,
        )

    conn = get_db_connection()
    blocker_message = get_stay_assignment_delete_blocker(conn, assignment_id)
    if blocker_message is not None:
        conn.close()
        return redirect_with_message(
            "reservations_page",
            blocker_message,
            "error",
            reservationId=reservation_id,
            assignmentId=assignment_id,
            search=search_text,
        )

    conn.execute(
        "DELETE FROM stay_room_assignment WHERE stayAssignmentId = ?",
        (assignment_id,),
    )
    conn.commit()
    conn.close()

    return redirect_with_message(
        "reservations_page",
        "Room assignment deleted.",
        reservationId=reservation_id,
        search=search_text,
    )


@app.route("/reservations/occupant/create", methods=["POST"])
def create_assignment_guest():
    reservation_id = parse_optional_int(request.form.get("reservationId"))
    assignment_id = parse_optional_int(request.form.get("stayAssignmentId"))
    guest_id = parse_optional_int(request.form.get("guestId"))
    occupant_role = clean_text(request.form.get("occupantRole"))
    search_text = clean_text(request.form.get("search"))

    if (
        reservation_id is None
        or assignment_id is None
        or guest_id is None
        or occupant_role not in OCCUPANT_ROLE_TYPES
    ):
        return redirect_with_message(
            "reservations_page",
            "Choose an assignment, a guest, and an occupant role.",
            "error",
            reservationId=reservation_id,
            assignmentId=assignment_id,
            search=search_text,
        )

    conn = get_db_connection()
    if occupant_role == "PRIMARY":
        primary_row = conn.execute(
            """
            SELECT guestId
            FROM stay_room_guest
            WHERE stayAssignmentId = ?
              AND occupantRole = 'PRIMARY'
            LIMIT 1
            """,
            (assignment_id,),
        ).fetchone()
        if primary_row is not None and primary_row["guestId"] != guest_id:
            conn.close()
            return redirect_with_message(
                "reservations_page",
                "This assignment already has a primary guest.",
                "error",
                reservationId=reservation_id,
                assignmentId=assignment_id,
                search=search_text,
            )

    try:
        conn.execute(
            """
            INSERT INTO stay_room_guest (stayAssignmentId, guestId, occupantRole)
            VALUES (?, ?, ?)
            """,
            (assignment_id, guest_id, occupant_role),
        )
        conn.commit()
    except sqlite3.Error:
        conn.rollback()
        conn.close()
        return redirect_with_message(
            "reservations_page",
            "Guest could not be linked to the assignment.",
            "error",
            reservationId=reservation_id,
            assignmentId=assignment_id,
            search=search_text,
        )

    conn.close()
    return redirect_with_message(
        "reservations_page",
        "Guest linked to assignment.",
        reservationId=reservation_id,
        assignmentId=assignment_id,
        search=search_text,
    )


@app.route("/reservations/occupant/delete", methods=["POST"])
def delete_assignment_guest():
    reservation_id = parse_optional_int(request.form.get("reservationId"))
    assignment_id = parse_optional_int(request.form.get("stayAssignmentId"))
    guest_id = parse_optional_int(request.form.get("guestId"))
    search_text = clean_text(request.form.get("search"))

    if reservation_id is None or assignment_id is None or guest_id is None:
        return redirect_with_message(
            "reservations_page",
            "Choose an assignment guest before deleting.",
            "error",
            reservationId=reservation_id,
            assignmentId=assignment_id,
            search=search_text,
        )

    conn = get_db_connection()
    conn.execute(
        "DELETE FROM stay_room_guest WHERE stayAssignmentId = ? AND guestId = ?",
        (assignment_id, guest_id),
    )
    conn.commit()
    conn.close()

    return redirect_with_message(
        "reservations_page",
        "Guest removed from assignment.",
        reservationId=reservation_id,
        assignmentId=assignment_id,
        search=search_text,
    )


@app.route("/billing/account/create", methods=["POST"])
def create_account():
    account_name = clean_text(request.form.get("accountName"))
    account_status = clean_text(request.form.get("accountStatus"))
    reservation_id = parse_optional_int(request.form.get("reservationId"))
    event_id = parse_optional_int(request.form.get("eventId"))
    responsible_party_id = parse_optional_int(request.form.get("responsiblePartyId"))
    responsibility_type = clean_text(request.form.get("responsibilityType"))
    search_text = clean_text(request.form.get("search"))

    try:
        responsibility_percent = parse_optional_float(request.form.get("responsibilityPercent"))
    except ValueError:
        return redirect_with_message(
            "billing",
            "Responsibility percent must be a number.",
            "error",
            search=search_text,
        )

    if (
        not account_name
        or account_status not in ACCOUNT_STATUS_TYPES
        or responsible_party_id is None
        or responsibility_type not in RESPONSIBILITY_TYPES
    ):
        return redirect_with_message(
            "billing",
            "Fill in the required account fields.",
            "error",
            search=search_text,
        )

    if (reservation_id is None and event_id is None) or (
        reservation_id is not None and event_id is not None
    ):
        return redirect_with_message(
            "billing",
            "Choose either a reservation or an event for the account.",
            "error",
            search=search_text,
        )

    if responsibility_percent is not None and (
        responsibility_percent < 0 or responsibility_percent > 100
    ):
        return redirect_with_message(
            "billing",
            "Responsibility percent must be between 0 and 100.",
            "error",
            search=search_text,
        )

    opened_at = get_current_timestamp()
    closed_at = None if account_status == "OPEN" else opened_at

    conn = get_db_connection()
    try:
        account_id = get_next_id(conn, "account", "accountId")
        conn.execute(
            """
            INSERT INTO account (
                accountId, reservationId, eventId, accountName,
                accountStatus, openedAt, closedAt
            ) VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                account_id,
                reservation_id,
                event_id,
                account_name,
                account_status,
                opened_at,
                closed_at,
            ),
        )
        conn.execute(
            """
            INSERT INTO account_responsibility (
                accountId, partyId, responsibilityType, responsibilityPercent
            ) VALUES (?, ?, ?, ?)
            """,
            (
                account_id,
                responsible_party_id,
                responsibility_type,
                responsibility_percent,
            ),
        )
        conn.commit()
    except sqlite3.Error:
        conn.rollback()
        conn.close()
        return redirect_with_message(
            "billing",
            "Account could not be added.",
            "error",
            search=search_text,
        )

    conn.close()
    return redirect_with_message(
        "billing",
        "Account added.",
        accountId=account_id,
        search=search_text,
    )


@app.route("/billing/account/update", methods=["POST"])
def update_account():
    account_id = parse_optional_int(request.form.get("accountId"))
    account_name = clean_text(request.form.get("accountName"))
    account_status = clean_text(request.form.get("accountStatus"))
    closed_at = parse_datetime_input(request.form.get("closedAt"))
    search_text = clean_text(request.form.get("search"))

    if account_id is None:
        return redirect_with_message(
            "billing",
            "Choose an account before updating.",
            "error",
            search=search_text,
        )

    if not account_name or account_status not in ACCOUNT_STATUS_TYPES:
        return redirect_with_message(
            "billing",
            "Fill in the required account fields.",
            "error",
            accountId=account_id,
            search=search_text,
        )

    conn = get_db_connection()
    account_row = conn.execute(
        "SELECT openedAt FROM account WHERE accountId = ?",
        (account_id,),
    ).fetchone()
    if account_row is None:
        conn.close()
        return redirect_with_message(
            "billing",
            "Selected account was not found.",
            "error",
            search=search_text,
        )

    if account_status == "OPEN":
        closed_at = None
    elif closed_at is None:
        closed_at = get_current_timestamp()

    if closed_at is not None and closed_at < account_row["openedAt"]:
        conn.close()
        return redirect_with_message(
            "billing",
            "Closed time cannot be earlier than opened time.",
            "error",
            accountId=account_id,
            search=search_text,
        )

    try:
        conn.execute(
            """
            UPDATE account
            SET accountName = ?, accountStatus = ?, closedAt = ?
            WHERE accountId = ?
            """,
            (account_name, account_status, closed_at, account_id),
        )
        conn.commit()
    except sqlite3.Error:
        conn.rollback()
        conn.close()
        return redirect_with_message(
            "billing",
            "Account update failed.",
            "error",
            accountId=account_id,
            search=search_text,
        )

    conn.close()
    return redirect_with_message(
        "billing",
        "Account updated.",
        accountId=account_id,
        search=search_text,
    )


@app.route("/billing/account/delete", methods=["POST"])
def delete_account():
    account_id = parse_optional_int(request.form.get("accountId"))
    search_text = clean_text(request.form.get("search"))

    if account_id is None:
        return redirect_with_message(
            "billing",
            "Choose an account before deleting.",
            "error",
            search=search_text,
        )

    conn = get_db_connection()
    blocker_message = get_account_delete_blocker(conn, account_id)
    if blocker_message is not None:
        conn.close()
        return redirect_with_message(
            "billing",
            blocker_message,
            "error",
            accountId=account_id,
            search=search_text,
        )

    try:
        conn.execute("DELETE FROM account_responsibility WHERE accountId = ?", (account_id,))
        conn.execute("DELETE FROM account WHERE accountId = ?", (account_id,))
        conn.commit()
    except sqlite3.Error:
        conn.rollback()
        conn.close()
        return redirect_with_message(
            "billing",
            "Account could not be deleted.",
            "error",
            accountId=account_id,
            search=search_text,
        )

    conn.close()
    return redirect_with_message(
        "billing",
        "Account deleted.",
        search=search_text,
    )


@app.route("/billing/charge/create", methods=["POST"])
def create_charge():
    account_id = parse_optional_int(request.form.get("accountId"))
    charge_type = clean_text(request.form.get("chargeType"))
    description = optional_text(request.form.get("description"))
    charge_time = parse_datetime_input(request.form.get("chargeTime"))
    used_by_guest_id = parse_optional_int(request.form.get("usedByGuestId"))
    stay_assignment_id = parse_optional_int(request.form.get("stayAssignmentId"))
    event_id = parse_optional_int(request.form.get("eventId"))
    employee_id = parse_optional_int(request.form.get("createdByEmployeeId"))
    search_text = clean_text(request.form.get("search"))

    try:
        amount = parse_optional_float(request.form.get("amount"))
    except ValueError:
        return redirect_with_message(
            "billing",
            "Charge amount must be a number.",
            "error",
            accountId=account_id,
            search=search_text,
        )

    if (
        account_id is None
        or charge_type not in CHARGE_TYPES
        or amount is None
        or amount < 0
        or charge_time is None
    ):
        return redirect_with_message(
            "billing",
            "Choose an account and fill in the required charge fields.",
            "error",
            accountId=account_id,
            search=search_text,
        )

    conn = get_db_connection()
    account_row = conn.execute(
        "SELECT reservationId, eventId FROM account WHERE accountId = ?",
        (account_id,),
    ).fetchone()
    if account_row is None:
        conn.close()
        return redirect_with_message(
            "billing",
            "Selected account was not found.",
            "error",
            search=search_text,
        )

    linked_event_id = event_id
    if account_row["reservationId"] is not None:
        if event_id is not None:
            conn.close()
            return redirect_with_message(
                "billing",
                "Reservation accounts should not link charges to an event.",
                "error",
                accountId=account_id,
                search=search_text,
            )
        if stay_assignment_id is not None:
            assignment_row = conn.execute(
                """
                SELECT 1
                FROM stay_room_assignment
                WHERE stayAssignmentId = ?
                  AND reservationId = ?
                LIMIT 1
                """,
                (stay_assignment_id, account_row["reservationId"]),
            ).fetchone()
            if assignment_row is None:
                conn.close()
                return redirect_with_message(
                    "billing",
                    "Stay assignment must belong to the account reservation.",
                    "error",
                    accountId=account_id,
                    search=search_text,
                )
    else:
        if stay_assignment_id is not None:
            conn.close()
            return redirect_with_message(
                "billing",
                "Event accounts should not link charges to a stay assignment.",
                "error",
                accountId=account_id,
                search=search_text,
            )
        linked_event_id = account_row["eventId"]
        if event_id is not None and event_id != account_row["eventId"]:
            conn.close()
            return redirect_with_message(
                "billing",
                "Event charges must use the same event as the account.",
                "error",
                accountId=account_id,
                search=search_text,
            )

    try:
        charge_id = get_next_id(conn, "charge", "chargeId")
        conn.execute(
            """
            INSERT INTO charge (
                chargeId, accountId, chargeType, description, amount,
                chargeTime, usedByGuestId, stayAssignmentId, eventId, createdByEmployeeId
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                charge_id,
                account_id,
                charge_type,
                description,
                amount,
                charge_time,
                used_by_guest_id,
                stay_assignment_id,
                linked_event_id,
                employee_id,
            ),
        )
        conn.commit()
    except sqlite3.Error:
        conn.rollback()
        conn.close()
        return redirect_with_message(
            "billing",
            "Charge could not be added.",
            "error",
            accountId=account_id,
            search=search_text,
        )

    conn.close()
    return redirect_with_message(
        "billing",
        "Charge added.",
        accountId=account_id,
        search=search_text,
    )


@app.route("/billing/charge/delete", methods=["POST"])
def delete_charge():
    account_id = parse_optional_int(request.form.get("accountId"))
    charge_id = parse_optional_int(request.form.get("chargeId"))
    search_text = clean_text(request.form.get("search"))

    if account_id is None or charge_id is None:
        return redirect_with_message(
            "billing",
            "Choose a charge before deleting.",
            "error",
            accountId=account_id,
            search=search_text,
        )

    conn = get_db_connection()
    conn.execute(
        "DELETE FROM charge WHERE chargeId = ? AND accountId = ?",
        (charge_id, account_id),
    )
    conn.commit()
    conn.close()

    return redirect_with_message(
        "billing",
        "Charge deleted.",
        accountId=account_id,
        search=search_text,
    )


@app.route("/billing/payment/create", methods=["POST"])
def create_payment():
    account_id = parse_optional_int(request.form.get("accountId"))
    paid_by_party_id = parse_optional_int(request.form.get("paidByPartyId"))
    payment_method = clean_text(request.form.get("paymentMethod"))
    payment_time = parse_datetime_input(request.form.get("paymentTime"))
    reference_number = optional_text(request.form.get("referenceNumber"))
    search_text = clean_text(request.form.get("search"))

    try:
        amount = parse_optional_float(request.form.get("amount"))
    except ValueError:
        return redirect_with_message(
            "billing",
            "Payment amount must be a number.",
            "error",
            accountId=account_id,
            search=search_text,
        )

    if (
        account_id is None
        or paid_by_party_id is None
        or not payment_method
        or amount is None
        or amount <= 0
        or payment_time is None
    ):
        return redirect_with_message(
            "billing",
            "Fill in the required payment fields.",
            "error",
            accountId=account_id,
            search=search_text,
        )

    conn = get_db_connection()
    try:
        payment_id = get_next_id(conn, "payment", "paymentId")
        conn.execute(
            """
            INSERT INTO payment (
                paymentId, accountId, paidByPartyId, paymentMethod,
                amount, paymentTime, referenceNumber
            ) VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                payment_id,
                account_id,
                paid_by_party_id,
                payment_method,
                amount,
                payment_time,
                reference_number,
            ),
        )
        conn.commit()
    except sqlite3.Error:
        conn.rollback()
        conn.close()
        return redirect_with_message(
            "billing",
            "Payment could not be added.",
            "error",
            accountId=account_id,
            search=search_text,
        )

    conn.close()
    return redirect_with_message(
        "billing",
        "Payment added.",
        accountId=account_id,
        search=search_text,
    )


@app.route("/billing/payment/delete", methods=["POST"])
def delete_payment():
    account_id = parse_optional_int(request.form.get("accountId"))
    payment_id = parse_optional_int(request.form.get("paymentId"))
    search_text = clean_text(request.form.get("search"))

    if account_id is None or payment_id is None:
        return redirect_with_message(
            "billing",
            "Choose a payment before deleting.",
            "error",
            accountId=account_id,
            search=search_text,
        )

    conn = get_db_connection()
    conn.execute(
        "DELETE FROM payment WHERE paymentId = ? AND accountId = ?",
        (payment_id, account_id),
    )
    conn.commit()
    conn.close()

    return redirect_with_message(
        "billing",
        "Payment deleted.",
        accountId=account_id,
        search=search_text,
    )


@app.errorhandler(Exception)
def handle_error(error):
    current_date = get_current_date()
    status_code = error.code if isinstance(error, HTTPException) else 500
    return (
        render_template(
            "error.html",
            error=error,
            snapshotDate=current_date,
            pageTitle="Error",
        ),
        status_code,
    )


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8080))
    app.run(host="0.0.0.0", port=port, debug=True)
