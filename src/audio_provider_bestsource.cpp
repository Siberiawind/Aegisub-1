// Copyright (c) 2022, arch1t3cht <arch1t3cht@gmail.com>
//
// Permission to use, copy, modify, and distribute this software for any
// purpose with or without fee is hereby granted, provided that the above
// copyright notice and this permission notice appear in all copies.
//
// THE SOFTWARE IS PROVIDED "AS IS" AND THE AUTHOR DISCLAIMS ALL WARRANTIES
// WITH REGARD TO THIS SOFTWARE INCLUDING ALL IMPLIED WARRANTIES OF
// MERCHANTABILITY AND FITNESS. IN NO EVENT SHALL THE AUTHOR BE LIABLE FOR
// ANY SPECIAL, DIRECT, INDIRECT, OR CONSEQUENTIAL DAMAGES OR ANY DAMAGES
// WHATSOEVER RESULTING FROM LOSS OF USE, DATA OR PROFITS, WHETHER IN AN
// ACTION OF CONTRACT, NEGLIGENCE OR OTHER TORTIOUS ACTION, ARISING OUT OF
// OR IN CONNECTION WITH THE USE OR PERFORMANCE OF THIS SOFTWARE.
//
// Aegisub Project http://www.aegisub.org/

/// @file audio_provider_bestsource.cpp
/// @brief BS-based audio provider
/// @ingroup audio_input bestsource
///

#ifdef WITH_BESTSOURCE
#include <libaegisub/audio/provider.h>

#include "audiosource.h"

#include "bestsource_common.h"
#include "compat.h"
#include "options.h"

#include <libaegisub/fs.h>
#include <libaegisub/make_unique.h>
#include <libaegisub/background_runner.h>
#include <libaegisub/log.h>

#include <map>

namespace {
class BSAudioProvider final : public agi::AudioProvider {
	std::map<std::string, std::string> bsopts;
	BestAudioSource bs;
	AudioProperties properties;

	void FillBuffer(void *Buf, int64_t Start, int64_t Count) const override;
public:
	BSAudioProvider(agi::fs::path const& filename, agi::BackgroundRunner *br);

	bool NeedsCache() const override { return OPT_GET("Provider/Audio/BestSource/Aegisub Cache")->GetBool(); }
};

/// @brief Constructor
/// @param filename The filename to open
BSAudioProvider::BSAudioProvider(agi::fs::path const& filename, agi::BackgroundRunner *br) try
: bsopts()
, bs(filename.string(), -1, -1, 0, GetBSCacheFile(filename), &bsopts)
{
	bs.SetMaxCacheSize(OPT_GET("Provider/Audio/BestSource/Max Cache Size")->GetInt() << 20);
	br->Run([&](agi::ProgressSink *ps) {
		ps->SetTitle(from_wx(_("Indexing")));
		ps->SetMessage(from_wx(_("Creating cache... This can take a while!")));
		ps->SetIndeterminate();
		if (bs.GetExactDuration()) {
			LOG_D("bs") << "File cached and has exact samples.";
		}
	});
	BSCleanCache();
	properties = bs.GetAudioProperties();
	float_samples = properties.IsFloat;
	bytes_per_sample = properties.BytesPerSample;
	sample_rate = properties.SampleRate;
	channels = properties.Channels;
	num_samples = properties.NumSamples;
	decoded_samples = OPT_GET("Provider/Audio/BestSource/Aegisub Cache")->GetBool() ? 0 : num_samples;
}
catch (AudioException const& err) {
	throw agi::AudioProviderError("Failed to create BestAudioSource");
}

void BSAudioProvider::FillBuffer(void *Buf, int64_t Start, int64_t Count) const {
	const_cast<BestAudioSource &>(bs).GetPackedAudio(reinterpret_cast<uint8_t *>(Buf), Start, Count);
}

}

std::unique_ptr<agi::AudioProvider> CreateBSAudioProvider(agi::fs::path const& file, agi::BackgroundRunner *br) {
	return agi::make_unique<BSAudioProvider>(file, br);
}

#endif /* WITH_BESTSOURCE */

