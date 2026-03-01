import createThumbnail from './thumbnail';
import {withProjectExportAuthorization} from '../tw-export-guard';

const spritePayload = (id, vm) => {
    const target = vm.runtime.getTargetById(id);
    if (!target) return null;

    return withProjectExportAuthorization(() => vm.exportSprite(
        id,
        'base64'
    )).then(zippedSprite => {
        const payload = {
            type: 'sprite',
            name: target.sprite.name,
            mime: 'application/zip',
            body: zippedSprite,
            // Filled in below
            thumbnail: ''
        };

        const costumeDataUrl = target.sprite.costumes[target.currentCostume].asset.encodeDataURI();

        return createThumbnail(costumeDataUrl).then(thumbnail => {
            payload.thumbnail = thumbnail;
            return payload;
        });
    });
};

export default spritePayload;
