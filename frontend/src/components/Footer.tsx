import { Link } from "react-router-dom";
import { Mic } from "lucide-react";
import { useI18n } from "@/lib/i18n";

const Footer = () => {
  const { t } = useI18n();
  return (
    <footer className="border-t border-border/50 pb-16 pt-12">
      <div className="container mx-auto px-4">
        <div className="flex flex-col md:flex-row items-center justify-between gap-6">
          <div className="flex items-center gap-2">
            <div className="w-7 h-7 rounded-lg gradient-bg flex items-center justify-center">
              <Mic className="w-4 h-4 text-primary-foreground" />
            </div>
            <span className="font-display font-semibold text-foreground">
              Access<span className="gradient-text">AI</span>
            </span>
          </div>

          <div className="flex flex-wrap items-center justify-center gap-6 text-sm text-muted-foreground">
            <Link to="/about" className="hover:text-foreground transition-colors">{t("footer.about")}</Link>
            <Link to="/privacy" className="hover:text-foreground transition-colors">{t("footer.privacy")}</Link>
            <Link to="/disclaimer" className="hover:text-foreground transition-colors">{t("footer.disclaimer")}</Link>

          </div>

          <p className="text-xs text-muted-foreground/60">© 2026 AccessAI</p>
        </div>
      </div>
    </footer>
  );
};

export default Footer;
