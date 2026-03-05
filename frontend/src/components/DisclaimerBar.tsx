import { useI18n } from "@/lib/i18n";

const DisclaimerBar = () => {
  const { t } = useI18n();
  return (
    <div className="disclaimer-bar">
      <p className="text-xs sm:text-sm max-w-3xl mx-auto">
        {t("disclaimer.text")}
      </p>
    </div>
  );
};

export default DisclaimerBar;
