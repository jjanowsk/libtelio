use std::ffi::CStr;

use libc::{c_char, c_void};
use telio;
use telio::TelioTracingSubscriber;

mod test_module {
    use std::sync::atomic::{AtomicUsize, Ordering};

    use super::*;

    #[test]
    fn test_logger() {
        let call_count = AtomicUsize::new(0);
        unsafe extern "C" fn test_telio_logger_fn(
            ctx: *mut c_void,
            level: telio::ffi_types::telio_log_level,
            message: *const c_char,
        ) {
            assert_eq!(telio::ffi_types::telio_log_level::TELIO_LOG_INFO, level);
            let message = CStr::from_ptr(message);
            assert_eq!(
                r#""logger::test_module":36 test message"#,
                message.to_str().unwrap()
            );
            let call_count: &AtomicUsize = &*(ctx as *const AtomicUsize);
            assert_eq!(0, call_count.fetch_add(1, Ordering::Relaxed));
        }
        let logger = telio::ffi_types::telio_logger_cb {
            ctx: &call_count as *const AtomicUsize as *mut c_void,
            cb: test_telio_logger_fn,
        };
        let tracing_subscriber = TelioTracingSubscriber::new(logger, tracing::Level::INFO);
        tracing::subscriber::set_global_default(tracing_subscriber).unwrap();

        tracing::info!("test message");
        assert_eq!(1, call_count.load(Ordering::Relaxed));
        tracing::debug!("this will be ignored since it's below info");
    }
}
