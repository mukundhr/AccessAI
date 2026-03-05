import { Link, useLocation } from "react-router-dom";
import { Mic } from "lucide-react";
import { motion } from "framer-motion";
import { useI18n, LanguageSwitcher } from "@/lib/i18n";

const Navbar = () => {
  const location = useLocation();
  const { t } = useI18n();

  return (
    <motion.nav
      initial={{ y: -20, opacity: 0 }}
      animate={{ y: 0, opacity: 1 }}
      transition={{ duration: 0.5 }}
      className="fixed top-0 left-0 right-0 z-50 glass-card border-b border-border/50"
      style={{ borderRadius: 0 }}
    >
      <div className="container mx-auto flex items-center justify-between py-3 px-4">
        <Link to="/" className="flex items-center gap-2.5">
          <div className="w-9 h-9 rounded-xl gradient-bg flex items-center justify-center">
            <Mic className="w-5 h-5 text-primary-foreground" />
          </div>
          <span className="font-display font-bold text-lg text-foreground">
            Access<span className="gradient-text">AI</span>
          </span>
        </Link>

        <div className="flex items-center gap-3">
          <LanguageSwitcher />
          <Link
            to="/about"
            className="text-sm text-muted-foreground hover:text-foreground transition-colors hidden sm:inline"
          >
            {t("nav.about")}
          </Link>
          {location.pathname !== "/upload" && (
            <Link
              to="/upload"
              className="btn-primary-gradient px-4 py-2 text-sm font-medium"
            >
              {t("nav.startNow")}
            </Link>
          )}
        </div>
      </div>
    </motion.nav>
  );
};

export default Navbar;
