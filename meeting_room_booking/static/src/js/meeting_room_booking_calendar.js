/** @odoo-module **/

import { registry } from "@web/core/registry";
import { calendarView } from "@web/views/calendar/calendar_view";
import { CalendarController } from "@web/views/calendar/calendar_controller";
import { CalendarCommonRenderer } from "@web/views/calendar/calendar_common/calendar_common_renderer";
import { useService, useBus } from "@web/core/utils/hooks";
import { useState, onWillStart } from "@odoo/owl";

export class MeetingRoomBookingCalendarController extends CalendarController {
    setup() {
        super.setup();
        this.orm = useService("orm");
        this.dashboardState = useState({
            data: {
                total_meetings_today: 0,
                active_meetings: 0,
                upcoming_meetings: 0,
                available_rooms: 0,
                occupied_rooms: 0
            }
        });

        onWillStart(async () => {
            await this.loadDashboardData();
        });

        // Listen for updates on the calendar model to automatically refresh dashboard counters
        useBus(this.model.bus, "update", async () => {
            await this.loadDashboardData();
        });
    }

    async loadDashboardData() {
        try {
            const data = await this.orm.call(
                "meeting.room.booking",
                "get_dashboard_summary",
                []
            );
            if (data) {
                Object.assign(this.dashboardState.data, data);
            }
        } catch (e) {
            console.error("Failed to load meeting room booking dashboard data", e);
        }
    }
}

MeetingRoomBookingCalendarController.template = "meeting_room_booking.CalendarController";

export class MeetingRoomBookingCalendarRenderer extends CalendarCommonRenderer {
    onClick(info) {
        // Skip opening popover preview and directly open edit/form dialog
        this.props.editRecord(this.props.model.records[info.event.id]);
    }
}

export const meetingRoomBookingCalendarView = {
    ...calendarView,
    Controller: MeetingRoomBookingCalendarController,
    Renderer: MeetingRoomBookingCalendarRenderer,
};

registry.category("views").add("meeting_room_booking_calendar", meetingRoomBookingCalendarView);
