import time
import logging
from datetime import datetime
import os
from test_upload import InstagramUploader

def setup_logging():
    """로깅 설정"""
    log_dir = "logs"
    os.makedirs(log_dir, exist_ok=True)

    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(message)s',
        handlers=[
            logging.FileHandler(os.path.join(
                log_dir,
                f'instagram_scheduler_daemon_{datetime.now().strftime("%Y%m%d")}.log'
            )),
            logging.StreamHandler()
        ]
    )
    return logging.getLogger(__name__)

def run_scheduler():
    """스케줄러 데몬 실행"""
    logger = setup_logging()
    uploader = InstagramUploader()

    logger.info("✅ 스케줄러 데몬이 시작되었습니다.")

    try:
        while True:
            try:
                # 예약된 업로드 처리
                uploader.process_scheduled_uploads()

                # 60초 대기
                time.sleep(60)

            except Exception as e:
                logger.error(f"❌ 예약 처리 중 오류 발생: {str(e)}")
                # 오류 발생 시 5분 대기 후 재시도
                time.sleep(300)

    except KeyboardInterrupt:
        logger.info("👋 스케줄러 데몬이 종료됩니다.")

if __name__ == "__main__":
    run_scheduler()