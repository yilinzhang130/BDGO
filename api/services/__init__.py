"""
Report services registry.

Adding a new report:
    1. Create services/reports/my_report.py subclassing ReportService
    2. Import and register here in REPORT_SERVICES
    3. REST endpoint + Chat tool + frontend card all pick it up.
"""

from services.report_builder import ReportService
from services.reports.bd_synthesize import BDSynthesizeService
from services.reports.buyer_profile import BuyerProfileService
from services.reports.clinical_guidelines import ClinicalGuidelinesService
from services.reports.commercial_assessment import CommercialAssessmentService
from services.reports.company_analysis import CompanyAnalysisService
from services.reports.data_room import DataRoomService
from services.reports.dd_checklist import DDChecklistService
from services.reports.deal_evaluator import DealEvaluatorService
from services.reports.deal_teaser import DealTeaserService
from services.reports.disease_landscape import DiseaseLandscapeService
from services.reports.draft_codev import DraftCoDevService
from services.reports.draft_license import DraftLicenseService
from services.reports.draft_mta import DraftMTAService
from services.reports.draft_spa import DraftSPAService
from services.reports.draft_ts import DraftTSService
from services.reports.import_reply import ImportReplyService
from services.reports.ip_landscape import IPLandscapeService
from services.reports.legal_review import LegalReviewService
from services.reports.outreach_email import OutreachEmailService
from services.reports.outreach_list import OutreachListService
from services.reports.outreach_log import OutreachLogService
from services.reports.paper_analysis import PaperAnalysisService
from services.reports.rnpv_valuation import RNPVValuationService
from services.reports.target_radar import TargetRadarService
from services.reports.timing_advisor import TimingAdvisorService

REPORT_SERVICES: dict[str, ReportService] = {
    PaperAnalysisService.slug: PaperAnalysisService(),
    BDSynthesizeService.slug: BDSynthesizeService(),
    BuyerProfileService.slug: BuyerProfileService(),
    ClinicalGuidelinesService.slug: ClinicalGuidelinesService(),
    CommercialAssessmentService.slug: CommercialAssessmentService(),
    CompanyAnalysisService.slug: CompanyAnalysisService(),
    DataRoomService.slug: DataRoomService(),
    DDChecklistService.slug: DDChecklistService(),
    DealEvaluatorService.slug: DealEvaluatorService(),
    DealTeaserService.slug: DealTeaserService(),
    DiseaseLandscapeService.slug: DiseaseLandscapeService(),
    DraftCoDevService.slug: DraftCoDevService(),
    DraftLicenseService.slug: DraftLicenseService(),
    DraftMTAService.slug: DraftMTAService(),
    DraftSPAService.slug: DraftSPAService(),
    DraftTSService.slug: DraftTSService(),
    ImportReplyService.slug: ImportReplyService(),
    IPLandscapeService.slug: IPLandscapeService(),
    LegalReviewService.slug: LegalReviewService(),
    OutreachEmailService.slug: OutreachEmailService(),
    OutreachListService.slug: OutreachListService(),
    OutreachLogService.slug: OutreachLogService(),
    RNPVValuationService.slug: RNPVValuationService(),
    TargetRadarService.slug: TargetRadarService(),
    TimingAdvisorService.slug: TimingAdvisorService(),
}


def get_service(slug: str) -> ReportService | None:
    return REPORT_SERVICES.get(slug)


def list_services() -> list[ReportService]:
    return list(REPORT_SERVICES.values())
